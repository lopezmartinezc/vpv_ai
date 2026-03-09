"""Incremental sync from MySQL production to PostgreSQL app database.

Unlike the full migration (migrate.py), this script:
- Does NOT drop or recreate tables
- Only UPDATEs player_stats that changed (played/scored data)
- Only INSERTs missing lineups (ON CONFLICT DO NOTHING)
- Updates match results for new matchdays
- Recalculates participant_matchday_scores

Usage:
    python incremental_sync.py                     # sync all pending matchdays
    python incremental_sync.py --matchdays 26      # sync only J26
    python incremental_sync.py --matchdays 25,26   # sync J25 and J26
    python incremental_sync.py --dry-run            # preview without committing
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import Counter

import os
from pathlib import Path

import mysql.connector
import psycopg
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection config — loads from migration/.env.sync
# Falls back to migration/.env if .env.sync doesn't exist.
# ---------------------------------------------------------------------------

_env_dir = Path(__file__).resolve().parent.parent
_sync_env = _env_dir / ".env.sync"
_default_env = _env_dir / ".env"
load_dotenv(_sync_env if _sync_env.exists() else _default_env)


def _get_mysql_config() -> dict:
    return {
        "host": os.getenv("MYSQL_HOST", "franquiciadonpiso.com"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "vpvadmin"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "ligavpv"),
        "charset": "utf8mb4",
    }


def _get_pg_conninfo() -> str:
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5433")
    user = os.getenv("PG_USER", "vpv")
    password = os.getenv("PG_PASSWORD", "vpv_secret")
    database = os.getenv("PG_DATABASE", "ligavpv")
    return f"host={host} port={port} user={user} password={password} dbname={database}"


SEASON = "2025-2026"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCORE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


def _parse_score(resultado: str | None) -> tuple[int | None, int | None]:
    if not resultado:
        return None, None
    m = _SCORE_RE.match(resultado)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _safe_int(val: object, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _bool(val: object) -> bool:
    return bool(val)


_FORMATION_POSITIONS = ("POR", "DEF", "MED", "DEL")


def _build_formation(positions: list[str]) -> str:
    counts: Counter[str] = Counter(positions)
    parts = [str(counts.get(pos, 0)) for pos in _FORMATION_POSITIONS]
    return "-".join(parts)


# ---------------------------------------------------------------------------
# Context maps (built from existing PG data)
# ---------------------------------------------------------------------------


def build_context(pg_conn: psycopg.Connection, season_name: str) -> dict:
    """Build lookup maps from existing PostgreSQL data."""
    ctx: dict = {}

    with pg_conn.cursor() as cur:
        # Season
        cur.execute("SELECT id FROM seasons WHERE name = %s", (season_name,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Season '{season_name}' not found in PG")
        ctx["season_id"] = row[0]
        log.info("Season '%s' -> id=%d", season_name, ctx["season_id"])

        # Matchday map: number -> id
        cur.execute(
            "SELECT number, id FROM matchdays WHERE season_id = %s",
            (ctx["season_id"],),
        )
        ctx["matchday_map"] = {r[0]: r[1] for r in cur.fetchall()}
        log.info("Loaded %d matchday mappings", len(ctx["matchday_map"]))

        # Team map: name -> id
        cur.execute(
            "SELECT name, id FROM teams WHERE season_id = %s",
            (ctx["season_id"],),
        )
        ctx["team_map"] = {r[0]: r[1] for r in cur.fetchall()}
        log.info("Loaded %d team mappings", len(ctx["team_map"]))

        # Match team lookup: (matchday_id, team_id) -> match_id
        cur.execute(
            """SELECT m.matchday_id, m.home_team_id, m.away_team_id, m.id
               FROM matches m
               JOIN matchdays md ON m.matchday_id = md.id
               WHERE md.season_id = %s""",
            (ctx["season_id"],),
        )
        ctx["match_team_lookup"] = {}
        ctx["match_by_teams"] = {}  # (matchday_id, home_id, away_id) -> match_id
        for md_id, home_id, away_id, match_id in cur.fetchall():
            ctx["match_team_lookup"][(md_id, home_id)] = match_id
            ctx["match_team_lookup"][(md_id, away_id)] = match_id
            ctx["match_by_teams"][(md_id, home_id, away_id)] = match_id

        # Player map: slug -> id
        cur.execute(
            "SELECT slug, id FROM players WHERE season_id = %s",
            (ctx["season_id"],),
        )
        ctx["player_map"] = {r[0]: r[1] for r in cur.fetchall()}
        log.info("Loaded %d player mappings", len(ctx["player_map"]))

        # Participant map: display_name -> participant_id
        cur.execute(
            """SELECT u.display_name, sp.id
               FROM season_participants sp
               JOIN users u ON sp.user_id = u.id
               WHERE sp.season_id = %s""",
            (ctx["season_id"],),
        )
        ctx["participant_by_name"] = {r[0]: r[1] for r in cur.fetchall()}
        log.info("Loaded %d participant mappings", len(ctx["participant_by_name"]))

    return ctx


def build_slot_to_participant(
    mysql_conn: mysql.connector.MySQLConnection,
    ctx: dict,
    season_name: str,
) -> dict[int, int]:
    """Map MySQL slot IDs to PG participant IDs via display_name matching."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, TRIM(nombre) as nombre FROM usuarios_temp WHERE temporada = %s",
        (season_name,),
    )
    slot_map: dict[int, int] = {}
    for row in cursor.fetchall():
        slot_id = row["id"]
        nombre = row["nombre"]
        participant_id = ctx["participant_by_name"].get(nombre)
        if participant_id:
            slot_map[slot_id] = participant_id
        else:
            log.warning("No PG participant found for MySQL slot %d ('%s')", slot_id, nombre)
    cursor.close()
    log.info("Mapped %d MySQL slots to PG participants", len(slot_map))
    return slot_map


# ---------------------------------------------------------------------------
# Sync functions
# ---------------------------------------------------------------------------


def sync_match_results(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: dict,
    matchdays: list[int],
) -> int:
    """Update match results (scores) from MySQL for specified matchdays."""
    cursor = mysql_conn.cursor(dictionary=True)
    updated = 0

    for md_num in matchdays:
        md_id = ctx["matchday_map"].get(md_num)
        if not md_id:
            log.warning("Matchday %d not found in PG, skipping", md_num)
            continue

        cursor.execute(
            """SELECT TRIM(eq_local) AS eq_local, TRIM(eq_vis) AS eq_vis,
                      resultado, contabiliza, est_ok, id_part, url_part
               FROM list_jornadas_temp
               WHERE temporada = %s AND jornada = %s""",
            (SEASON, md_num),
        )

        with pg_conn.cursor() as pg_cur:
            for row in cursor.fetchall():
                home_score, away_score = _parse_score(row["resultado"])
                home_team_id = ctx["team_map"].get(row["eq_local"])
                away_team_id = ctx["team_map"].get(row["eq_vis"])
                if not home_team_id or not away_team_id:
                    continue

                match_id = ctx["match_by_teams"].get((md_id, home_team_id, away_team_id))
                if not match_id:
                    log.warning(
                        "Match not found: J%d %s vs %s", md_num, row["eq_local"], row["eq_vis"]
                    )
                    continue

                pg_cur.execute(
                    """UPDATE matches
                       SET home_score = %s, away_score = %s,
                           result = %s, counts = %s, stats_ok = %s,
                           source_id = %s, source_url = %s
                       WHERE id = %s AND (home_score IS DISTINCT FROM %s
                                          OR away_score IS DISTINCT FROM %s
                                          OR stats_ok IS DISTINCT FROM %s)""",
                    (
                        home_score,
                        away_score,
                        row["resultado"],
                        _bool(row["contabiliza"]),
                        _bool(row["est_ok"]),
                        row["id_part"],
                        row["url_part"],
                        match_id,
                        home_score,
                        away_score,
                        _bool(row["est_ok"]),
                    ),
                )
                updated += pg_cur.rowcount

    cursor.close()
    log.info("Updated %d match results", updated)
    return updated


def sync_player_stats(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: dict,
    matchdays: list[int],
) -> int:
    """Update player_stats with played/scored data from MySQL for specified matchdays."""
    cursor = mysql_conn.cursor(dictionary=True)
    updated = 0

    for md_num in matchdays:
        md_id = ctx["matchday_map"].get(md_num)
        if not md_id:
            log.warning("Matchday %d not found in PG, skipping", md_num)
            continue

        cursor.execute(
            """SELECT nom_url, TRIM(equipo) AS equipo, pos, play, evento, min_evento,
                      tiempo_jug, res_l, res_v, res, gol_f, gol_c,
                      gol, gol_p, pen_fall, gol_pp, asis, pen_par,
                      ama, ama_remove, ama_doble, roja, tiro_palo,
                      pen_for, pen_com, est_marca, picas_as, estadistica,
                      ptos_marca, ptos_as, marca_as,
                      ptos_jor, ptos_jugar, ptos_titular, ptos_resultado,
                      ptos_imbatibilidad, ptos_gol, ptos_gol_p,
                      ptos_pen_fall, ptos_gol_pp, ptos_asis, ptos_pen_par,
                      ptos_ama, ptos_roja, ptos_tiro_palo, ptos_pen_for, ptos_pen_com
               FROM jornadas_temp
               WHERE temporada = %s AND jornada = %s AND play = 1""",
            (SEASON, md_num),
        )

        rows = cursor.fetchall()
        log.info("J%d: %d played rows from MySQL", md_num, len(rows))

        with pg_conn.cursor() as pg_cur:
            for row in rows:
                player_id = ctx["player_map"].get(row["nom_url"])
                if not player_id:
                    continue

                # Resolve match_id via team
                team_id = ctx["team_map"].get(row["equipo"])
                match_id = ctx["match_team_lookup"].get((md_id, team_id)) if team_id else None

                pg_cur.execute(
                    """UPDATE player_stats
                       SET processed = %s, position = %s, played = %s,
                           event = %s, event_minute = %s, minutes_played = %s,
                           home_score = %s, away_score = %s, result = %s,
                           goals_for = %s, goals_against = %s,
                           goals = %s, penalty_goals = %s, penalties_missed = %s,
                           own_goals = %s, assists = %s, penalties_saved = %s,
                           yellow_card = %s, yellow_removed = %s,
                           double_yellow = %s, red_card = %s,
                           woodwork = %s, penalties_won = %s,
                           penalties_committed = %s,
                           marca_rating = %s, as_picas = %s,
                           match_id = %s,
                           pts_play = %s, pts_starter = %s, pts_result = %s,
                           pts_clean_sheet = %s, pts_goals = %s,
                           pts_penalty_goals = %s, pts_penalties_missed = %s,
                           pts_own_goals = %s, pts_assists = %s,
                           pts_penalties_saved = %s, pts_yellow = %s,
                           pts_red = %s, pts_woodwork = %s,
                           pts_penalties_won = %s, pts_pen_committed = %s,
                           pts_marca = %s, pts_as = %s,
                           pts_marca_as = %s, pts_total = %s
                       WHERE player_id = %s AND matchday_id = %s""",
                    (
                        _bool(row["estadistica"]),
                        row["pos"],
                        True,  # played = True (we only fetched play=1)
                        row["evento"],
                        row["min_evento"],
                        row["tiempo_jug"],
                        row["res_l"],
                        row["res_v"],
                        row["res"],
                        row["gol_f"],
                        row["gol_c"],
                        row["gol"],
                        row["gol_p"],
                        row["pen_fall"],
                        row["gol_pp"],
                        row["asis"],
                        row["pen_par"],
                        _bool(row["ama"]),
                        _bool(row["ama_remove"]),
                        _bool(row["ama_doble"]),
                        _bool(row["roja"]),
                        row["tiro_palo"],
                        row["pen_for"],
                        row["pen_com"],
                        row["est_marca"],
                        row["picas_as"],
                        match_id,
                        row["ptos_jugar"],
                        row["ptos_titular"],
                        row["ptos_resultado"],
                        row["ptos_imbatibilidad"],
                        row["ptos_gol"],
                        row["ptos_gol_p"],
                        row["ptos_pen_fall"],
                        row["ptos_gol_pp"],
                        row["ptos_asis"],
                        row["ptos_pen_par"],
                        row["ptos_ama"],
                        row["ptos_roja"],
                        row["ptos_tiro_palo"],
                        row["ptos_pen_for"],
                        row["ptos_pen_com"],
                        _safe_int(row["ptos_marca"]),
                        _safe_int(row["ptos_as"]),
                        _safe_int(row["marca_as"]),
                        row["ptos_jor"],
                        # WHERE clause
                        player_id,
                        md_id,
                    ),
                )
                updated += pg_cur.rowcount

        log.info("J%d: updated %d player_stats rows", md_num, updated)

    cursor.close()
    log.info("Total player_stats updated: %d", updated)
    return updated


def sync_lineups(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: dict,
    slot_map: dict[int, int],
    matchdays: list[int],
) -> int:
    """Import missing lineups from MySQL for specified matchdays."""
    cursor = mysql_conn.cursor(dictionary=True)
    inserted_lineups = 0

    for md_num in matchdays:
        md_id = ctx["matchday_map"].get(md_num)
        if not md_id:
            continue

        cursor.execute(
            """SELECT nom_url, pos, id_user, order_astudillo
               FROM jornadas_temp
               WHERE temporada = %s AND jornada = %s AND alineado = 1 AND id_user > 0
               ORDER BY id_user, order_astudillo""",
            (SEASON, md_num),
        )

        # Group by id_user
        from itertools import groupby

        rows = cursor.fetchall()
        keyfunc = lambda r: r["id_user"]
        rows_sorted = sorted(rows, key=keyfunc)

        with pg_conn.cursor() as pg_cur:
            for slot_id, group in groupby(rows_sorted, key=keyfunc):
                participant_id = slot_map.get(slot_id)
                if not participant_id:
                    log.warning("No participant for slot %d, skipping", slot_id)
                    continue

                players = list(group)
                positions = [p["pos"] for p in players if p["pos"]]
                formation = _build_formation(positions)

                # Insert lineup (skip if already exists)
                pg_cur.execute(
                    """INSERT INTO lineups (participant_id, matchday_id, formation, confirmed, telegram_sent, total_points)
                       VALUES (%s, %s, %s, TRUE, FALSE, 0)
                       ON CONFLICT (participant_id, matchday_id) DO NOTHING
                       RETURNING id""",
                    (participant_id, md_id, formation),
                )
                result = pg_cur.fetchone()
                if not result:
                    # Lineup already exists, skip
                    continue

                lineup_id = result[0]
                inserted_lineups += 1

                # Insert lineup players
                for idx, p in enumerate(players):
                    player_id = ctx["player_map"].get(p["nom_url"])
                    if not player_id:
                        log.warning("Player slug '%s' not found", p["nom_url"])
                        continue
                    display_order = p["order_astudillo"] if p["order_astudillo"] else idx
                    pg_cur.execute(
                        """INSERT INTO lineup_players (lineup_id, player_id, position_slot, display_order, points)
                           VALUES (%s, %s, %s, %s, 0)
                           ON CONFLICT DO NOTHING""",
                        (lineup_id, player_id, p["pos"], display_order),
                    )

        log.info("J%d: inserted %d new lineups", md_num, inserted_lineups)

    cursor.close()

    # Bulk update lineup_player points from player_stats
    with pg_conn.cursor() as pg_cur:
        pg_cur.execute(
            """UPDATE lineup_players lp
               SET points = COALESCE(ps.pts_total, 0)
               FROM lineups l, player_stats ps
               WHERE lp.lineup_id = l.id
                 AND ps.player_id = lp.player_id
                 AND ps.matchday_id = l.matchday_id
                 AND l.matchday_id IN (
                     SELECT id FROM matchdays
                     WHERE season_id = %s AND number = ANY(%s)
                 )""",
            (ctx["season_id"], matchdays),
        )
        log.info("Updated lineup_players points: %d rows", pg_cur.rowcount)

        # Update lineup totals
        pg_cur.execute(
            """UPDATE lineups l
               SET total_points = sub.total
               FROM (
                   SELECT lp.lineup_id, SUM(lp.points) AS total
                   FROM lineup_players lp
                   JOIN lineups ll ON lp.lineup_id = ll.id
                   WHERE ll.matchday_id IN (
                       SELECT id FROM matchdays
                       WHERE season_id = %s AND number = ANY(%s)
                   )
                   GROUP BY lp.lineup_id
               ) sub
               WHERE l.id = sub.lineup_id""",
            (ctx["season_id"], matchdays),
        )
        log.info("Updated lineup totals: %d rows", pg_cur.rowcount)

    log.info("Total new lineups inserted: %d", inserted_lineups)
    return inserted_lineups


def recalculate_scores(
    pg_conn: psycopg.Connection,
    ctx: dict,
    matchdays: list[int],
) -> int:
    """Recalculate participant_matchday_scores for specified matchdays."""
    with pg_conn.cursor() as pg_cur:
        # Upsert scores
        pg_cur.execute(
            """INSERT INTO participant_matchday_scores (participant_id, matchday_id, total_points)
               SELECT
                   l.participant_id,
                   l.matchday_id,
                   COALESCE(SUM(
                       CASE WHEN m.counts = TRUE THEN ps.pts_total ELSE 0 END
                   ), 0) AS total_points
               FROM lineups l
               JOIN lineup_players lp ON lp.lineup_id = l.id
               LEFT JOIN player_stats ps ON ps.player_id = lp.player_id
                                         AND ps.matchday_id = l.matchday_id
               LEFT JOIN matches m ON m.id = ps.match_id
               WHERE l.matchday_id IN (
                   SELECT id FROM matchdays
                   WHERE season_id = %s AND number = ANY(%s)
               )
               GROUP BY l.participant_id, l.matchday_id
               ON CONFLICT (participant_id, matchday_id) DO UPDATE
                   SET total_points = EXCLUDED.total_points""",
            (ctx["season_id"], matchdays),
        )
        upserted = pg_cur.rowcount
        log.info("Upserted %d participant_matchday_scores", upserted)

        # Update rankings
        pg_cur.execute(
            """UPDATE participant_matchday_scores pms
               SET ranking = sub.rnk
               FROM (
                   SELECT id,
                          RANK() OVER (
                              PARTITION BY matchday_id
                              ORDER BY total_points DESC
                          )::SMALLINT AS rnk
                   FROM participant_matchday_scores
                   WHERE matchday_id IN (
                       SELECT id FROM matchdays
                       WHERE season_id = %s AND number = ANY(%s)
                   )
               ) sub
               WHERE pms.id = sub.id""",
            (ctx["season_id"], matchdays),
        )
        log.info("Updated %d rankings", pg_cur.rowcount)

    return upserted


def update_matchday_stats_ok(
    pg_conn: psycopg.Connection,
    ctx: dict,
    matchdays: list[int],
) -> int:
    """Set matchdays.stats_ok = TRUE when all counting matches have stats_ok."""
    with pg_conn.cursor() as pg_cur:
        pg_cur.execute(
            """UPDATE matchdays md
               SET stats_ok = TRUE
               WHERE md.season_id = %s
                 AND md.number = ANY(%s)
                 AND md.stats_ok = FALSE
                 AND NOT EXISTS (
                     SELECT 1 FROM matches m
                     WHERE m.matchday_id = md.id
                       AND m.counts = TRUE
                       AND m.stats_ok = FALSE
                 )
                 AND EXISTS (
                     SELECT 1 FROM matches m
                     WHERE m.matchday_id = md.id
                       AND m.counts = TRUE
                       AND m.stats_ok = TRUE
                 )""",
            (ctx["season_id"], matchdays),
        )
        updated = pg_cur.rowcount
        if updated:
            log.info("Marked %d matchday(s) as stats_ok", updated)
        return updated


def update_season_metadata(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: dict,
) -> None:
    """Update season matchday_current and matchday_scanned from MySQL production."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT jornada_actual FROM temporadas WHERE temporada = %s",
        (SEASON,),
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return

    new_current = row["jornada_actual"]
    with pg_conn.cursor() as pg_cur:
        pg_cur.execute(
            "UPDATE seasons SET matchday_current = %s WHERE id = %s AND matchday_current < %s",
            (new_current, ctx["season_id"], new_current),
        )
        if pg_cur.rowcount:
            log.info("Updated matchday_current to %d", new_current)
        else:
            log.info("matchday_current already >= %d", new_current)

        # Advance matchday_scanned to highest consecutive matchday with stats_ok
        pg_cur.execute(
            """SELECT number FROM matchdays
               WHERE season_id = %s AND stats_ok = TRUE
               ORDER BY number""",
            (ctx["season_id"],),
        )
        completed = [r[0] for r in pg_cur.fetchall()]
        scanned = 0
        for n in completed:
            if scanned == 0 or n == scanned + 1:
                scanned = n
            else:
                break
        if scanned > 0:
            pg_cur.execute(
                "UPDATE seasons SET matchday_scanned = %s WHERE id = %s AND matchday_scanned < %s",
                (scanned, ctx["season_id"], scanned),
            )
            if pg_cur.rowcount:
                log.info("Updated matchday_scanned to %d", scanned)
            else:
                log.info("matchday_scanned already >= %d", scanned)


# ---------------------------------------------------------------------------
# Detect which matchdays need syncing
# ---------------------------------------------------------------------------


def detect_pending_matchdays(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: dict,
) -> list[int]:
    """Find matchdays where MySQL has more played stats than PG."""
    # MySQL played counts per matchday
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT jornada, SUM(play) as played
           FROM jornadas_temp
           WHERE temporada = %s
           GROUP BY jornada
           HAVING SUM(play) > 0
           ORDER BY jornada""",
        (SEASON,),
    )
    mysql_played = {row["jornada"]: int(row["played"]) for row in cursor.fetchall()}
    cursor.close()

    # PG played counts per matchday
    with pg_conn.cursor() as pg_cur:
        pg_cur.execute(
            """SELECT m.number, COUNT(*) FILTER (WHERE ps.played) as played
               FROM matchdays m
               LEFT JOIN player_stats ps ON ps.matchday_id = m.id
               WHERE m.season_id = %s
               GROUP BY m.number
               ORDER BY m.number""",
            (ctx["season_id"],),
        )
        pg_played = {r[0]: r[1] for r in pg_cur.fetchall()}

    pending = []
    for md_num, mysql_count in mysql_played.items():
        pg_count = pg_played.get(md_num, 0)
        if mysql_count > pg_count:
            pending.append(md_num)
            log.info(
                "J%d: MySQL has %d played, PG has %d -> NEEDS SYNC",
                md_num, mysql_count, pg_count,
            )

    if not pending:
        log.info("All matchdays are in sync!")

    return pending


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incremental sync: MySQL production -> PostgreSQL app"
    )
    parser.add_argument(
        "--matchdays",
        type=str,
        default=None,
        metavar="N,N,...",
        help="Comma-separated matchday numbers to sync (default: auto-detect)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    dry_run: bool = args.dry_run

    if dry_run:
        log.info("DRY-RUN mode — changes will be rolled back.")

    # Connect
    log.info("Connecting to MySQL production...")
    try:
        mysql_conn = mysql.connector.connect(**_get_mysql_config())
    except mysql.connector.Error as exc:
        log.error("Could not connect to MySQL: %s", exc)
        sys.exit(1)

    log.info("Connecting to PostgreSQL app...")
    try:
        pg_conn = psycopg.connect(_get_pg_conninfo(), autocommit=False)
    except psycopg.Error as exc:
        log.error("Could not connect to PostgreSQL: %s", exc)
        mysql_conn.close()
        sys.exit(1)

    try:
        # Build context from PG
        ctx = build_context(pg_conn, SEASON)
        slot_map = build_slot_to_participant(mysql_conn, ctx, SEASON)

        # Determine matchdays to sync
        if args.matchdays:
            matchdays = [int(x.strip()) for x in args.matchdays.split(",")]
        else:
            matchdays = detect_pending_matchdays(mysql_conn, pg_conn, ctx)

        if not matchdays:
            log.info("Nothing to sync. Exiting.")
            return

        log.info("=" * 60)
        log.info("Syncing matchdays: %s", matchdays)
        log.info("=" * 60)

        # 1. Match results
        log.info("--- STEP 1: Match results ---")
        sync_match_results(mysql_conn, pg_conn, ctx, matchdays)

        # 2. Player stats
        log.info("--- STEP 2: Player stats ---")
        sync_player_stats(mysql_conn, pg_conn, ctx, matchdays)

        # 3. Lineups
        log.info("--- STEP 3: Lineups ---")
        sync_lineups(mysql_conn, pg_conn, ctx, slot_map, matchdays)

        # 4. Recalculate scores
        log.info("--- STEP 4: Recalculate scores ---")
        recalculate_scores(pg_conn, ctx, matchdays)

        # 5. Update matchdays.stats_ok
        log.info("--- STEP 5: Update matchdays.stats_ok ---")
        update_matchday_stats_ok(pg_conn, ctx, matchdays)

        # 6. Season metadata
        log.info("--- STEP 6: Season metadata ---")
        update_season_metadata(mysql_conn, pg_conn, ctx)

        if dry_run:
            pg_conn.rollback()
            log.info("DRY-RUN complete — all changes rolled back.")
        else:
            pg_conn.commit()
            log.info("All changes committed successfully!")

    except Exception:
        log.exception("Sync failed!")
        pg_conn.rollback()
        sys.exit(1)
    finally:
        pg_conn.close()
        mysql_conn.close()
        log.info("Connections closed.")


if __name__ == "__main__":
    main()
