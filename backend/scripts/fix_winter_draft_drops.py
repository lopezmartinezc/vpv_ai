"""Fix winter draft: release dropped players + populate ownership log.

Compares each participant's roster at jornada_cambios-1 vs jornada_cambios.
Players in BEFORE but not AFTER = DROPPED -> set owner_id = NULL.

Also populates player_ownership_log with two periods:
  1. jornada_inicial: pre-winter roster
  2. jornada_cambios: post-winter roster (+ NULL for dropped players)

Usage:
    cd backend
    python -m scripts.fix_winter_draft_drops              # dry-run
    python -m scripts.fix_winter_draft_drops --apply       # apply
    python -m scripts.fix_winter_draft_drops --season 2024-2025 --apply
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import mysql.connector
import psycopg
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent / "migration" / ".env"
load_dotenv(_env_path)


def _get_mysql_config() -> dict:
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "vpvadmin"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "ligavpv"),
        "charset": "utf8mb4",
        "use_unicode": True,
    }


def _get_pg_conninfo() -> str:
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5433")
    user = os.getenv("PG_USER", "vpv")
    password = os.getenv("PG_PASSWORD", "vpv_secret")
    database = os.getenv("PG_DATABASE", "ligavpv")
    return f"host={host} port={port} user={user} password={password} dbname={database}"


def _get_mysql_roster(mcur, temporada: str, jornada: int) -> dict[int, set[str]]:
    """Get roster per user at a given matchday. Returns {mysql_uid: {slug, ...}}."""
    mcur.execute(
        "SELECT nom_url, id_user FROM jornadas_temp "
        "WHERE temporada = %s AND jornada = %s AND id_user > 0",
        (temporada, jornada),
    )
    rosters: dict[int, set[str]] = {}
    for r in mcur.fetchall():
        rosters.setdefault(r["id_user"], set()).add(r["nom_url"])
    return rosters


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix winter draft drops + populate ownership log"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--season", type=str, default=None)
    args = parser.parse_args()

    mysql_conn = mysql.connector.connect(**_get_mysql_config())
    pg_conn = psycopg.connect(_get_pg_conninfo())

    try:
        with pg_conn.cursor() as pcur:
            if args.season:
                pcur.execute("SELECT id, name FROM seasons WHERE name = %s", (args.season,))
            else:
                pcur.execute("SELECT id, name FROM seasons ORDER BY id")
            seasons = pcur.fetchall()

        if not seasons:
            print("No seasons found.")
            return

        total_released = 0
        total_log = 0
        for season_id, season_name in seasons:
            released, log_entries = fix_season(
                mysql_conn, pg_conn, season_id=season_id,
                temporada=season_name, dry_run=not args.apply,
            )
            total_released += released
            total_log += log_entries

        print(f"\n{'='*60}")
        if not args.apply:
            print(f"[DRY-RUN] Total: {total_released} releases, {total_log} log entries.")
            print("Use --apply to execute.")
        else:
            print(f"Done. {total_released} releases, {total_log} log entries.")

    finally:
        mysql_conn.close()
        pg_conn.close()


def fix_season(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    *,
    season_id: int,
    temporada: str,
    dry_run: bool = True,
) -> tuple[int, int]:
    """Fix drops + populate log for one season. Returns (released, log_entries)."""
    mcur = mysql_conn.cursor(dictionary=True)
    pcur = pg_conn.cursor()
    prefix = "[DRY-RUN] " if dry_run else ""

    print(f"\n{'='*60}")
    print(f"Season: {temporada} (id={season_id})")
    print(f"{'='*60}")

    # --- Get season metadata from MySQL ---
    mcur.execute(
        "SELECT jornada_inicial, jornada_cambios FROM temporadas WHERE temporada = %s",
        (temporada,),
    )
    row = mcur.fetchone()
    if not row or not row["jornada_cambios"] or not row["jornada_inicial"]:
        print("  Missing jornada_inicial or jornada_cambios — skipping.")
        mcur.close()
        pcur.close()
        return 0, 0

    j_inicial = int(row["jornada_inicial"])
    j_cambios = int(row["jornada_cambios"])
    j_antes = j_cambios - 1
    print(f"  jornada_inicial={j_inicial}, jornada_cambios={j_cambios}")

    # --- Build user mapping ---
    mcur.execute(
        "SELECT id, nombre FROM usuarios_temp WHERE temporada = %s ORDER BY id",
        (temporada,),
    )
    mysql_users = {r["id"]: r["nombre"].strip() for r in mcur.fetchall()}

    pcur.execute(
        "SELECT sp.id, u.display_name FROM season_participants sp "
        "JOIN users u ON u.id = sp.user_id WHERE sp.season_id = %s",
        (season_id,),
    )
    pg_name_to_pid = {name: pid for pid, name in pcur.fetchall()}
    uid_to_pid = {}
    for uid, name in mysql_users.items():
        if name in pg_name_to_pid:
            uid_to_pid[uid] = pg_name_to_pid[name]
    pid_to_name = {v: k for k, v in pg_name_to_pid.items()}
    print(f"  Mapped {len(uid_to_pid)}/{len(mysql_users)} users")

    # --- Get PG player map ---
    pcur.execute(
        "SELECT slug, id, owner_id FROM players WHERE season_id = %s",
        (season_id,),
    )
    slug_to_player = {slug: (pid, owner) for slug, pid, owner in pcur.fetchall()}

    # --- Read rosters ---
    roster_inicial = _get_mysql_roster(mcur, temporada, j_inicial)
    roster_antes = _get_mysql_roster(mcur, temporada, j_antes)
    roster_cambios = _get_mysql_roster(mcur, temporada, j_cambios)

    if not roster_antes or not roster_cambios:
        print(f"  No roster data for J{j_antes} or J{j_cambios} — skipping.")
        mcur.close()
        pcur.close()
        return 0, 0

    # --- Detect drops and picks ---
    # Build set of ALL picked slugs across all participants
    all_picked: set[str] = set()
    all_dropped: dict[str, str] = {}  # slug -> participant name who dropped it
    draft_changes: list[tuple[str, set[str], set[str]]] = []

    for uid in sorted(roster_antes.keys()):
        before = roster_antes.get(uid, set())
        after = roster_cambios.get(uid, set())
        dropped = before - after
        picked = after - before
        name = mysql_users.get(uid, f"uid={uid}")
        all_picked |= picked
        for slug in dropped:
            all_dropped[slug] = name
        draft_changes.append((name, dropped, picked))

    print(f"\n  Draft changes (J{j_antes} vs J{j_cambios}):")
    released = 0
    for name, dropped, picked in draft_changes:
        if dropped or picked:
            print(f"    {name}:")
            for slug in sorted(dropped):
                print(f"      DROPPED: {slug}")
            for slug in sorted(picked):
                print(f"      PICKED:  {slug}")

    # Release dropped players ONLY if nobody picked them in the same draft
    for slug, dropper_name in sorted(all_dropped.items()):
        if slug in all_picked:
            # Another participant picked this player — don't release
            continue
        player_info = slug_to_player.get(slug)
        if not player_info:
            continue
        player_id, current_owner = player_info
        if current_owner is not None:
            owner_name = pid_to_name.get(current_owner, str(current_owner))
            print(f"    {prefix}RELEASE: {slug} (dropped by {dropper_name}, owner: {owner_name})")
            if not dry_run:
                pcur.execute(
                    "UPDATE players SET owner_id = NULL, is_available = TRUE "
                    "WHERE id = %s",
                    (player_id,),
                )
            released += 1

    # --- Populate ownership log ---
    log_entries = 0

    # Build flat ownership maps: slug -> participant_id
    pre_ownership: dict[str, int | None] = {}
    for uid, slugs in roster_inicial.items():
        pid = uid_to_pid.get(uid)
        for slug in slugs:
            pre_ownership[slug] = pid

    post_ownership: dict[str, int | None] = {}
    for uid, slugs in roster_cambios.items():
        pid = uid_to_pid.get(uid)
        for slug in slugs:
            post_ownership[slug] = pid

    for slug, (player_id, _) in slug_to_player.items():
        # Period 1: pre-winter ownership (from jornada_inicial)
        if slug in pre_ownership and pre_ownership[slug] is not None:
            if not dry_run:
                pcur.execute(
                    "INSERT INTO player_ownership_log "
                    "(season_id, player_id, participant_id, from_matchday) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (season_id, player_id, from_matchday) DO UPDATE "
                    "SET participant_id = EXCLUDED.participant_id",
                    (season_id, player_id, pre_ownership[slug], j_inicial),
                )
            log_entries += 1

        # Period 2: if ownership changed at winter draft
        pre_owner = pre_ownership.get(slug)
        post_owner = post_ownership.get(slug)
        if pre_owner != post_owner:
            if not dry_run:
                pcur.execute(
                    "INSERT INTO player_ownership_log "
                    "(season_id, player_id, participant_id, from_matchday) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (season_id, player_id, from_matchday) DO UPDATE "
                    "SET participant_id = EXCLUDED.participant_id",
                    (season_id, player_id, post_owner, j_cambios),
                )
            log_entries += 1

    if not dry_run and (released or log_entries):
        pg_conn.commit()

    # --- Final verification ---
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
        (season_id,),
    )
    has_over = False
    print("\n  Player counts:")
    for name, cnt in pcur.fetchall():
        marker = " <-- OVER" if cnt > 26 else ""
        if marker:
            has_over = True
        print(f"    {name}: {cnt}{marker}")

    if not has_over and released == 0:
        print("  OK")

    print(f"  Summary: {released} released, {log_entries} log entries")
    mcur.close()
    pcur.close()
    return released, log_entries


if __name__ == "__main__":
    main()
