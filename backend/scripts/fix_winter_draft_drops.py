"""Fix winter draft: set player ownership from MySQL post-winter roster (J23).

Since ownership only changes at the winter draft, J23 is the definitive
source of truth for the rest of the season.

Usage:
    cd backend
    source .venv/bin/activate
    python -m scripts.fix_winter_draft_drops              # dry-run
    python -m scripts.fix_winter_draft_drops --apply       # apply changes
"""

from __future__ import annotations

import argparse

import mysql.connector
import psycopg

MYSQL_DSN = {
    "host": "127.0.0.1",
    "port": 3307,
    "user": "root",
    "password": "migration",
    "database": "ligavpv",
}
PG_DSN = "host=localhost port=5433 user=vpv password=vpv_secret dbname=ligavpv"
SEASON_ID = 8
TEMPORADA = "2024-2025"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    mysql_conn = mysql.connector.connect(**MYSQL_DSN)
    pg_conn = psycopg.connect(PG_DSN)

    try:
        fix(mysql_conn, pg_conn, dry_run=not args.apply)
    finally:
        mysql_conn.close()
        pg_conn.close()


def fix(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    *,
    dry_run: bool = True,
) -> None:
    mcur = mysql_conn.cursor(dictionary=True)
    pcur = pg_conn.cursor()
    prefix = "[DRY-RUN] " if dry_run else ""

    # --- Build user mapping ---
    mcur.execute(
        "SELECT id, nombre FROM usuarios_temp WHERE temporada = %s ORDER BY id",
        (TEMPORADA,),
    )
    mysql_users = {r["id"]: r["nombre"].strip() for r in mcur.fetchall()}

    pcur.execute(
        "SELECT sp.id, u.display_name FROM season_participants sp "
        "JOIN users u ON u.id = sp.user_id WHERE sp.season_id = %s",
        (SEASON_ID,),
    )
    pg_name_to_pid = {name: pid for pid, name in pcur.fetchall()}
    uid_to_pid = {}
    for uid, name in mysql_users.items():
        if name in pg_name_to_pid:
            uid_to_pid[uid] = pg_name_to_pid[name]
    pid_to_name = {v: k for k, v in pg_name_to_pid.items()}
    print(f"Mapped {len(uid_to_pid)} users")

    # --- Get jornada_cambios ---
    mcur.execute(
        "SELECT jornada_cambios FROM temporadas WHERE temporada = %s",
        (TEMPORADA,),
    )
    jornada_cambios = int(mcur.fetchone()["jornada_cambios"])
    print(f"jornada_cambios = {jornada_cambios}")

    # --- Get post-winter ownership from MySQL (J23) ---
    # This is the definitive ownership since changes only happen at winter draft
    mcur.execute(
        "SELECT DISTINCT nom_url, id_user FROM jornadas_temp "
        "WHERE temporada = %s AND jornada = %s AND id_user > 0",
        (TEMPORADA, jornada_cambios),
    )
    j23_ownership: dict[str, int] = {}  # slug -> mysql_uid
    for r in mcur.fetchall():
        j23_ownership[r["nom_url"]] = r["id_user"]

    # Count per user in MySQL J23
    user_counts: dict[int, int] = {}
    for uid in j23_ownership.values():
        user_counts[uid] = user_counts.get(uid, 0) + 1
    print(f"\nMySQL J{jornada_cambios} rosters:")
    for uid in sorted(user_counts.keys()):
        print(f"  {mysql_users.get(uid, '?')}: {user_counts[uid]} players")

    # --- Get all PG players ---
    pcur.execute(
        "SELECT id, slug, name, owner_id FROM players WHERE season_id = %s",
        (SEASON_ID,),
    )
    pg_players = {
        slug: (pid, name, owner_id)
        for pid, slug, name, owner_id in pcur.fetchall()
    }

    # --- Sync ownership ---
    print(f"\n=== Syncing ownership ===")
    changes = 0

    for slug, (player_id, player_name, current_owner) in pg_players.items():
        if slug in j23_ownership:
            expected_owner = uid_to_pid.get(j23_ownership[slug])
            if expected_owner is None:
                continue
            if current_owner != expected_owner:
                old_name = pid_to_name.get(current_owner, str(current_owner))
                new_name = pid_to_name.get(expected_owner, str(expected_owner))
                print(f"  {prefix}{player_name}: {old_name} -> {new_name}")
                if not dry_run:
                    pcur.execute(
                        "UPDATE players SET owner_id = %s, is_available = FALSE "
                        "WHERE id = %s",
                        (expected_owner, player_id),
                    )
                changes += 1
        else:
            # Not in J23 roster — should be unowned
            if current_owner is not None:
                old_name = pid_to_name.get(current_owner, str(current_owner))
                print(f"  {prefix}{player_name}: RELEASE from {old_name}")
                if not dry_run:
                    pcur.execute(
                        "UPDATE players SET owner_id = NULL, is_available = TRUE "
                        "WHERE id = %s",
                        (player_id,),
                    )
                changes += 1

    # --- Create missing players (and missing teams if needed) ---
    missing = set(j23_ownership.keys()) - set(pg_players.keys())
    if missing:
        print(f"\n=== Creating {len(missing)} missing players ===")
        created = 0
        teams_created = 0
        for slug in sorted(missing):
            mcur.execute(
                "SELECT nom_url, nom_hum, TRIM(equipo) as equipo, pos "
                "FROM jornadas_temp WHERE temporada = %s AND jornada = %s "
                "AND nom_url = %s LIMIT 1",
                (TEMPORADA, jornada_cambios, slug),
            )
            r = mcur.fetchone()
            if not r:
                continue

            # Find or create team in PG
            pcur.execute(
                "SELECT id FROM teams WHERE LOWER(name) = LOWER(%s) AND season_id = %s",
                (r["equipo"], SEASON_ID),
            )
            team_row = pcur.fetchone()
            if not team_row:
                print(f"  {prefix}CREATE TEAM: {r['equipo']}")
                if not dry_run:
                    team_slug = r["equipo"].lower().replace(" ", "-")
                    pcur.execute(
                        "INSERT INTO teams (season_id, name, slug) "
                        "VALUES (%s, %s, %s) RETURNING id",
                        (SEASON_ID, r["equipo"], team_slug),
                    )
                    team_row = pcur.fetchone()
                    teams_created += 1
                else:
                    teams_created += 1
                    # Use placeholder for dry-run
                    team_row = None

            team_id = team_row[0] if team_row else None
            owner_pid = uid_to_pid.get(j23_ownership[slug])
            name = r["nom_hum"] or slug
            pos = r["pos"]

            print(
                f"  {prefix}CREATE: {name} ({pos}, {r['equipo']}) "
                f"-> {pid_to_name.get(owner_pid, '?')}"
            )
            if not dry_run:
                pcur.execute(
                    "INSERT INTO players (season_id, team_id, name, display_name, "
                    "slug, position, is_available, owner_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (SEASON_ID, team_id, name, name, slug, pos,
                     owner_pid is None, owner_pid),
                )
            created += 1

        print(f"  {prefix}Created {created} players, {teams_created} teams")

    if not dry_run:
        pg_conn.commit()
        print(f"\nAll changes committed. ({changes} ownership + {created} created)")
    else:
        print(f"\n[DRY-RUN] Would apply {changes} changes. Use --apply to execute.")

    # Final verification
    pcur.execute(
        """
        SELECT u.display_name, COUNT(p.id) as cnt
        FROM season_participants sp
        JOIN users u ON u.id = sp.user_id
        LEFT JOIN players p ON p.owner_id = sp.id
        WHERE sp.season_id = %s
        GROUP BY u.display_name
        ORDER BY cnt DESC
        """,
        (SEASON_ID,),
    )
    print("\nFinal player counts:")
    for name, cnt in pcur.fetchall():
        # Some participants may have <26 because some players aren't in PG
        marker = " <-- OVER" if cnt > 26 else ""
        print(f"  {name}: {cnt}{marker}")

    mcur.close()
    pcur.close()


if __name__ == "__main__":
    main()
