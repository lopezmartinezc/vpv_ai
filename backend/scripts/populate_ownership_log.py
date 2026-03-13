"""Populate player_ownership_log from MySQL jornadas_temp + PG draft_picks.

For seasons 1-7: derives ownership from MySQL jornadas_temp.id_user.
For season 8 (2025-2026): uses PG draft_picks (current season, managed in new app).

Two snapshots per season:
  1. PRESEASON (from_matchday = matchday_start):
     All players with id_user > 0 at matchday_start in MySQL.
  2. WINTER (from_matchday = matchday_winter):
     Ownership CHANGES between matchday_winter-1 and matchday_winter.

Run with migration venv (has both mysql.connector and psycopg):
  /path/to/migration/.venv/bin/python backend/scripts/populate_ownership_log.py
"""
from __future__ import annotations

import os
from pathlib import Path

import mysql.connector
import psycopg
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent / "migration" / ".env"
load_dotenv(_env_path)


def _get_pg_conninfo() -> str:
    if dsn := os.environ.get("PG_DSN"):
        return dsn
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    user = os.getenv("PG_USER", "vpv")
    password = os.getenv("PG_PASSWORD", "")
    database = os.getenv("PG_DATABASE", "ligavpv")
    return f"host={host} port={port} user={user} password={password} dbname={database}"


MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", ""),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "ligavpv"),
    "charset": "utf8mb4",
}

CURRENT_SEASON_NAME = "2025-2026"


def _get_mysql_ownership(mysql_conn):
    """Build preseason + winter ownership data from MySQL jornadas_temp."""
    cur = mysql_conn.cursor(dictionary=True)

    # Season metadata from MySQL
    cur.execute("SELECT temporada, jornada_cambios FROM temporadas ORDER BY temporada")
    seasons_meta = {r["temporada"]: r["jornada_cambios"] for r in cur.fetchall()}

    # First jornada with owned players per season
    cur.execute("""
        SELECT temporada, MIN(jornada) as first_owned
        FROM jornadas_temp WHERE id_user > 0 GROUP BY temporada
    """)
    first_owned = {r["temporada"]: r["first_owned"] for r in cur.fetchall()}

    preseason: dict[str, list[tuple[str, int]]] = {}  # temporada -> [(slug, slot_id)]
    winter: dict[str, list[tuple[str, int, int]]] = {}  # temporada -> [(slug, before, after)]

    for temporada, jornada_cambios in seasons_meta.items():
        if temporada == CURRENT_SEASON_NAME:
            continue

        md_start = first_owned.get(temporada)
        if md_start is None:
            continue

        # Preseason: owned players at matchday_start
        cur.execute(
            "SELECT nom_url, id_user FROM jornadas_temp "
            "WHERE temporada = %s AND jornada = %s AND id_user > 0",
            (temporada, md_start),
        )
        preseason[temporada] = [(r["nom_url"], r["id_user"]) for r in cur.fetchall()]

        # Winter: changes between jornada_cambios-1 and jornada_cambios
        if jornada_cambios and jornada_cambios > 0:
            before = jornada_cambios - 1
            cur.execute("""
                SELECT pre.nom_url,
                       pre.id_user AS owner_before,
                       COALESCE(post.id_user, 0) AS owner_after
                FROM jornadas_temp pre
                LEFT JOIN jornadas_temp post
                    ON pre.nom_url = post.nom_url
                    AND post.temporada = %s AND post.jornada = %s
                WHERE pre.temporada = %s AND pre.jornada = %s
                  AND COALESCE(pre.id_user, 0) != COALESCE(post.id_user, 0)
                  AND (pre.id_user > 0 OR COALESCE(post.id_user, 0) > 0)
                UNION
                SELECT post.nom_url,
                       COALESCE(pre.id_user, 0) AS owner_before,
                       post.id_user AS owner_after
                FROM jornadas_temp post
                LEFT JOIN jornadas_temp pre
                    ON post.nom_url = pre.nom_url
                    AND pre.temporada = %s AND pre.jornada = %s
                WHERE post.temporada = %s AND post.jornada = %s
                  AND COALESCE(pre.id_user, 0) != COALESCE(post.id_user, 0)
                  AND (COALESCE(pre.id_user, 0) > 0 OR post.id_user > 0)
            """, (
                temporada, jornada_cambios, temporada, before,
                temporada, before, temporada, jornada_cambios,
            ))
            winter[temporada] = [
                (r["nom_url"], r["owner_before"], r["owner_after"])
                for r in cur.fetchall()
            ]

    cur.close()
    return preseason, winter


def _build_slot_map(mysql_conn, pg_conn):
    """Map (temporada, mysql_slot_id) -> pg_participant_id via display_name."""
    # PG: user display_name -> user_id
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, display_name FROM users")
        pg_user_by_name = {r[1]: r[0] for r in cur.fetchall()}

        cur.execute("SELECT id, season_id, user_id FROM season_participants")
        pg_part = {(r[1], r[2]): r[0] for r in cur.fetchall()}

        cur.execute("SELECT id, name FROM seasons")
        season_by_name = {r[1]: r[0] for r in cur.fetchall()}

    # MySQL: (temporada, slot_id) -> display_name -> PG participant_id
    mcur = mysql_conn.cursor(dictionary=True)
    mcur.execute("SELECT id, temporada, nombre FROM usuarios_temp")
    slot_map: dict[tuple[str, int], int] = {}
    for r in mcur.fetchall():
        nombre = r["nombre"].strip()
        pg_uid = pg_user_by_name.get(nombre)
        if pg_uid is None:
            continue
        sid = season_by_name.get(r["temporada"])
        if sid is None:
            continue
        part_id = pg_part.get((sid, pg_uid))
        if part_id is not None:
            slot_map[(r["temporada"], r["id"])] = part_id
    mcur.close()

    return slot_map, season_by_name


def populate():
    mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
    pg_conn = psycopg.connect(_get_pg_conninfo())

    preseason_data, winter_data = _get_mysql_ownership(mysql_conn)
    slot_map, _ = _build_slot_map(mysql_conn, pg_conn)
    mysql_conn.close()

    with pg_conn.cursor() as cur:
        cur.execute("DELETE FROM player_ownership_log")

        # Build player lookup: (season_id, slug) -> player_id
        cur.execute("SELECT id, season_id, slug FROM players")
        player_by_slug = {(r[1], r[2]): r[0] for r in cur.fetchall()}

        # Get season metadata from PG
        cur.execute("SELECT id, name, matchday_start, matchday_winter FROM seasons ORDER BY id")
        seasons = cur.fetchall()  # (id, name, matchday_start, matchday_winter)

        total = 0

        # ---- Seasons 1-7: from MySQL ----
        for sid, sname, md_start, md_winter in seasons:
            if sname == CURRENT_SEASON_NAME:
                continue

            # Preseason entries
            entries = preseason_data.get(sname, [])
            for nom_url, mysql_slot in entries:
                player_id = player_by_slug.get((sid, nom_url))
                part_id = slot_map.get((sname, mysql_slot))
                if player_id is None or part_id is None:
                    continue
                cur.execute(
                    "INSERT INTO player_ownership_log "
                    "(season_id, player_id, participant_id, from_matchday) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT ON CONSTRAINT uq_ownership_log_player_matchday "
                    "DO UPDATE SET participant_id = EXCLUDED.participant_id",
                    (sid, player_id, part_id, md_start),
                )
                total += 1

            # Winter entries
            changes = winter_data.get(sname, [])
            # Drops first (owner_after == 0), then picks (owner_after > 0)
            drops = [(s, b, a) for s, b, a in changes if not a]
            picks = [(s, b, a) for s, b, a in changes if a]

            for nom_url, _before, _after in drops:
                player_id = player_by_slug.get((sid, nom_url))
                if player_id is None:
                    continue
                cur.execute(
                    "INSERT INTO player_ownership_log "
                    "(season_id, player_id, participant_id, from_matchday) "
                    "VALUES (%s, %s, NULL, %s) "
                    "ON CONFLICT ON CONSTRAINT uq_ownership_log_player_matchday "
                    "DO UPDATE SET participant_id = EXCLUDED.participant_id",
                    (sid, player_id, md_winter),
                )
                total += 1

            for nom_url, _before, owner_after in picks:
                player_id = player_by_slug.get((sid, nom_url))
                part_id = slot_map.get((sname, owner_after))
                if player_id is None or part_id is None:
                    continue
                cur.execute(
                    "INSERT INTO player_ownership_log "
                    "(season_id, player_id, participant_id, from_matchday) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT ON CONSTRAINT uq_ownership_log_player_matchday "
                    "DO UPDATE SET participant_id = EXCLUDED.participant_id",
                    (sid, player_id, part_id, md_winter),
                )
                total += 1

            pre_count = len([1 for s, m in entries if player_by_slug.get((sid, s)) and slot_map.get((sname, m))])
            winter_count = len(drops) + len(picks)
            print(f"  {sname}: {pre_count} preseason + {winter_count} winter changes")

        # ---- Season 8 (2025-2026): from draft_picks ----
        s8 = next((s for s in seasons if s[1] == CURRENT_SEASON_NAME), None)
        if s8:
            sid, sname, md_start, md_winter = s8

            # Preseason picks
            cur.execute(
                "SELECT dp.participant_id, dp.player_id "
                "FROM draft_picks dp JOIN drafts d ON dp.draft_id = d.id "
                "WHERE d.season_id = %s AND d.phase = 'preseason'",
                (sid,),
            )
            pre_picks = cur.fetchall()
            for part_id, player_id in pre_picks:
                cur.execute(
                    "INSERT INTO player_ownership_log "
                    "(season_id, player_id, participant_id, from_matchday) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT ON CONSTRAINT uq_ownership_log_player_matchday "
                    "DO UPDATE SET participant_id = EXCLUDED.participant_id",
                    (sid, player_id, part_id, md_start),
                )
                total += 1

            # Winter picks — drops first, then picks
            cur.execute(
                "SELECT dp.participant_id, dp.player_id, dp.dropped_player_id "
                "FROM draft_picks dp JOIN drafts d ON dp.draft_id = d.id "
                "WHERE d.season_id = %s AND d.phase = 'winter'",
                (sid,),
            )
            winter_picks = cur.fetchall()

            for _part_id, _player_id, dropped_id in winter_picks:
                if dropped_id is not None:
                    cur.execute(
                        "INSERT INTO player_ownership_log "
                        "(season_id, player_id, participant_id, from_matchday) "
                        "VALUES (%s, %s, NULL, %s) "
                        "ON CONFLICT ON CONSTRAINT uq_ownership_log_player_matchday "
                        "DO UPDATE SET participant_id = EXCLUDED.participant_id",
                        (sid, dropped_id, md_winter),
                    )
                    total += 1

            for part_id, player_id, _dropped_id in winter_picks:
                cur.execute(
                    "INSERT INTO player_ownership_log "
                    "(season_id, player_id, participant_id, from_matchday) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT ON CONSTRAINT uq_ownership_log_player_matchday "
                    "DO UPDATE SET participant_id = EXCLUDED.participant_id",
                    (sid, player_id, part_id, md_winter),
                )
                total += 1

            print(f"  {sname}: {len(pre_picks)} preseason + {len(winter_picks)} winter (from draft_picks)")

    pg_conn.commit()
    pg_conn.close()
    print(f"\nDone. {total} ownership log entries across {len(seasons)} seasons.")


if __name__ == "__main__":
    populate()
