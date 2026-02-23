"""
step_07_player_stats.py - THE BIG MIGRATION: jornadas_temp -> player_stats (~225K rows).

MySQL source table: jornadas_temp (all columns used)
    nom_url, jornada, temporada, equipo, pos, nom_hum, id_user,
    order_astudillo, alineado, estadistica, play, res_l, res_v, res,
    gol_f, gol_c, evento, min_evento, tiempo_jug, gol, gol_p, pen_fall,
    gol_pp, asis, pen_par, ama, ama_remove, ama_doble, roja, tiro_palo,
    pen_for, pen_com, est_marca, ptos_marca (VARCHAR), picas_as,
    ptos_as (VARCHAR), marca_as, ptos_jor, ptos_jugar, ptos_titular,
    ptos_resultado, ptos_imbatibilidad, ptos_gol, ptos_gol_p, ptos_pen_fall,
    ptos_gol_pp, ptos_asis, ptos_pen_par, ptos_ama, ptos_roja, ptos_tiro_palo,
    ptos_pen_for, ptos_pen_com

PostgreSQL target table: player_stats
    id                  SERIAL PK
    player_id           INT FK -> players.id
    matchday_id         INT FK -> matchdays.id
    match_id            INT FK nullable -> matches.id
    processed           BOOLEAN
    position            VARCHAR(3)
    played              BOOLEAN
    event               VARCHAR(60)
    event_minute        SMALLINT
    minutes_played      SMALLINT
    home_score          SMALLINT
    away_score          SMALLINT
    result              SMALLINT
    goals_for           SMALLINT
    goals_against       SMALLINT
    goals               SMALLINT
    penalty_goals       SMALLINT
    penalties_missed    SMALLINT
    own_goals           SMALLINT
    assists             SMALLINT
    penalties_saved     SMALLINT
    yellow_card         BOOLEAN
    yellow_removed      BOOLEAN
    double_yellow       BOOLEAN
    red_card            BOOLEAN
    woodwork            SMALLINT
    penalties_won       SMALLINT
    penalties_committed SMALLINT
    marca_rating        VARCHAR(10)
    as_picas            VARCHAR(10)
    pts_play            SMALLINT
    pts_starter         SMALLINT
    pts_result          SMALLINT
    pts_clean_sheet     SMALLINT
    pts_goals           SMALLINT
    pts_penalty_goals   SMALLINT
    pts_assists         SMALLINT
    pts_penalties_saved SMALLINT
    pts_woodwork        SMALLINT
    pts_penalties_won   SMALLINT
    pts_penalties_missed SMALLINT
    pts_own_goals       SMALLINT
    pts_yellow          SMALLINT
    pts_red             SMALLINT
    pts_pen_committed   SMALLINT
    pts_marca           SMALLINT
    pts_as              SMALLINT
    pts_marca_as        SMALLINT
    pts_total           SMALLINT
    UNIQUE(player_id, matchday_id)

Performance strategy:
    - Server-side (unbuffered) MySQL cursor to avoid loading ~225K rows into RAM.
    - psycopg executemany with batches of 5 000 rows.
    - Progress logged every 10 000 rows.
"""

import logging

import mysql.connector
import psycopg

from context import MigrationContext

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5_000
_LOG_INTERVAL = 10_000

# ---------------------------------------------------------------------------
# MySQL query — fetch all columns needed for player_stats
# ---------------------------------------------------------------------------

_MYSQL_QUERY = """
SELECT
    nom_url,
    jornada,
    temporada,
    TRIM(equipo)      AS equipo,
    estadistica,
    pos,
    play,
    evento,
    min_evento,
    tiempo_jug,
    res_l,
    res_v,
    res,
    gol_f,
    gol_c,
    gol,
    gol_p,
    pen_fall,
    gol_pp,
    asis,
    pen_par,
    ama,
    ama_remove,
    ama_doble,
    roja,
    tiro_palo,
    pen_for,
    pen_com,
    est_marca,
    ptos_marca,
    picas_as,
    ptos_as,
    marca_as,
    ptos_jor,
    ptos_jugar,
    ptos_titular,
    ptos_resultado,
    ptos_imbatibilidad,
    ptos_gol,
    ptos_gol_p,
    ptos_pen_fall,
    ptos_gol_pp,
    ptos_asis,
    ptos_pen_par,
    ptos_ama,
    ptos_roja,
    ptos_tiro_palo,
    ptos_pen_for,
    ptos_pen_com
FROM jornadas_temp
ORDER BY temporada, jornada, nom_url
"""

# ---------------------------------------------------------------------------
# PostgreSQL insert
# ---------------------------------------------------------------------------

_INSERT_STAT = """
INSERT INTO player_stats (
    player_id,
    matchday_id,
    match_id,
    processed,
    position,
    played,
    event,
    event_minute,
    minutes_played,
    home_score,
    away_score,
    result,
    goals_for,
    goals_against,
    goals,
    penalty_goals,
    penalties_missed,
    own_goals,
    assists,
    penalties_saved,
    yellow_card,
    yellow_removed,
    double_yellow,
    red_card,
    woodwork,
    penalties_won,
    penalties_committed,
    marca_rating,
    as_picas,
    pts_play,
    pts_starter,
    pts_result,
    pts_clean_sheet,
    pts_goals,
    pts_penalty_goals,
    pts_assists,
    pts_penalties_saved,
    pts_woodwork,
    pts_penalties_won,
    pts_penalties_missed,
    pts_own_goals,
    pts_yellow,
    pts_red,
    pts_pen_committed,
    pts_marca,
    pts_as,
    pts_marca_as,
    pts_total
)
VALUES (
    %(player_id)s,
    %(matchday_id)s,
    %(match_id)s,
    %(processed)s,
    %(position)s,
    %(played)s,
    %(event)s,
    %(event_minute)s,
    %(minutes_played)s,
    %(home_score)s,
    %(away_score)s,
    %(result)s,
    %(goals_for)s,
    %(goals_against)s,
    %(goals)s,
    %(penalty_goals)s,
    %(penalties_missed)s,
    %(own_goals)s,
    %(assists)s,
    %(penalties_saved)s,
    %(yellow_card)s,
    %(yellow_removed)s,
    %(double_yellow)s,
    %(red_card)s,
    %(woodwork)s,
    %(penalties_won)s,
    %(penalties_committed)s,
    %(marca_rating)s,
    %(as_picas)s,
    %(pts_play)s,
    %(pts_starter)s,
    %(pts_result)s,
    %(pts_clean_sheet)s,
    %(pts_goals)s,
    %(pts_penalty_goals)s,
    %(pts_assists)s,
    %(pts_penalties_saved)s,
    %(pts_woodwork)s,
    %(pts_penalties_won)s,
    %(pts_penalties_missed)s,
    %(pts_own_goals)s,
    %(pts_yellow)s,
    %(pts_red)s,
    %(pts_pen_committed)s,
    %(pts_marca)s,
    %(pts_as)s,
    %(pts_marca_as)s,
    %(pts_total)s
)
ON CONFLICT (player_id, matchday_id) DO NOTHING
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(val: object, default: int = 0) -> int:
    """Parse a value (possibly a VARCHAR) to int, returning default on failure."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _bool(val: object) -> bool:
    """Convert a MySQL tinyint/None to Python bool."""
    return bool(val)


# ---------------------------------------------------------------------------
# Main step
# ---------------------------------------------------------------------------

def run(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Migrate all rows from jornadas_temp into player_stats."""

    # ------------------------------------------------------------------
    # Use an unbuffered (server-side) cursor so MySQL streams rows one by
    # one instead of loading ~225K rows into memory at once.
    # ------------------------------------------------------------------
    mysql_cursor = mysql_conn.cursor(dictionary=True, buffered=False)
    mysql_cursor.execute(_MYSQL_QUERY)

    logger.info(
        "MySQL server-side cursor opened. Streaming jornadas_temp rows "
        "(batch_size=%d, log_interval=%d).",
        _BATCH_SIZE,
        _LOG_INTERVAL,
    )

    total_processed = 0
    total_inserted = 0
    total_skipped_player = 0
    total_skipped_matchday = 0
    total_conflict = 0

    batch: list[dict] = []

    def _flush_batch(pg_cur: psycopg.Cursor, rows: list[dict]) -> int:
        """Insert a batch of dicts into player_stats, return inserted count."""
        if not rows:
            return 0
        # executemany with a list of dicts — psycopg v3 accepts %(name)s style
        pg_cur.executemany(_INSERT_STAT, rows)
        # rowcount after executemany reflects the number of rows actually
        # inserted (ON CONFLICT DO NOTHING reduces this for conflicts).
        return pg_cur.rowcount if pg_cur.rowcount >= 0 else len(rows)

    with pg_conn.cursor() as pg_cur:
        for row in mysql_cursor:
            total_processed += 1

            nom_url: str = row["nom_url"]
            temporada: str = row["temporada"]
            jornada: int = row["jornada"]
            equipo: str = row["equipo"] or ""

            # -- Resolve player_id ----------------------------------------
            player_id = ctx.player_map.get((temporada, nom_url))
            if player_id is None:
                logger.debug(
                    "Player '%s' / season '%s' not in ctx.player_map — skipping stat row.",
                    nom_url,
                    temporada,
                )
                total_skipped_player += 1
                if total_processed % _LOG_INTERVAL == 0:
                    logger.info(
                        "Progress: %d rows processed | inserted=%d skipped_player=%d "
                        "skipped_matchday=%d",
                        total_processed,
                        total_inserted,
                        total_skipped_player,
                        total_skipped_matchday,
                    )
                continue

            # -- Resolve matchday_id --------------------------------------
            matchday_id = ctx.matchday_map.get((temporada, jornada))
            if matchday_id is None:
                logger.debug(
                    "Matchday jornada=%d / season '%s' not in ctx.matchday_map — "
                    "skipping stat row for player '%s'.",
                    jornada,
                    temporada,
                    nom_url,
                )
                total_skipped_matchday += 1
                if total_processed % _LOG_INTERVAL == 0:
                    logger.info(
                        "Progress: %d rows processed | inserted=%d skipped_player=%d "
                        "skipped_matchday=%d",
                        total_processed,
                        total_inserted,
                        total_skipped_player,
                        total_skipped_matchday,
                    )
                continue

            # -- Resolve match_id (optional) ------------------------------
            match_id: int | None = None
            team_id = ctx.team_map.get((temporada, equipo))
            if team_id is not None:
                match_id = ctx.match_team_lookup.get((matchday_id, team_id))

            # -- Build the param dict -------------------------------------
            stat: dict = {
                "player_id": player_id,
                "matchday_id": matchday_id,
                "match_id": match_id,
                "processed": _bool(row["estadistica"]),
                "position": row["pos"],
                "played": _bool(row["play"]),
                "event": row["evento"],
                "event_minute": row["min_evento"],
                "minutes_played": row["tiempo_jug"],
                "home_score": row["res_l"],
                "away_score": row["res_v"],
                "result": row["res"],
                "goals_for": row["gol_f"],
                "goals_against": row["gol_c"],
                "goals": row["gol"],
                "penalty_goals": row["gol_p"],
                "penalties_missed": row["pen_fall"],
                "own_goals": row["gol_pp"],
                "assists": row["asis"],
                "penalties_saved": row["pen_par"],
                "yellow_card": _bool(row["ama"]),
                "yellow_removed": _bool(row["ama_remove"]),
                "double_yellow": _bool(row["ama_doble"]),
                "red_card": _bool(row["roja"]),
                "woodwork": row["tiro_palo"],
                "penalties_won": row["pen_for"],
                "penalties_committed": row["pen_com"],
                "marca_rating": row["est_marca"],
                "as_picas": row["picas_as"],
                # VARCHAR columns need safe parsing
                "pts_marca": _safe_int(row["ptos_marca"]),
                "pts_as": _safe_int(row["ptos_as"]),
                "pts_marca_as": row["marca_as"],
                "pts_total": row["ptos_jor"],
                "pts_play": row["ptos_jugar"],
                "pts_starter": row["ptos_titular"],
                "pts_result": row["ptos_resultado"],
                "pts_clean_sheet": row["ptos_imbatibilidad"],
                "pts_goals": row["ptos_gol"],
                "pts_penalty_goals": row["ptos_gol_p"],
                "pts_penalties_missed": row["ptos_pen_fall"],
                "pts_own_goals": row["ptos_gol_pp"],
                "pts_assists": row["ptos_asis"],
                "pts_penalties_saved": row["ptos_pen_par"],
                "pts_yellow": row["ptos_ama"],
                "pts_red": row["ptos_roja"],
                "pts_woodwork": row["ptos_tiro_palo"],
                "pts_penalties_won": row["ptos_pen_for"],
                "pts_pen_committed": row["ptos_pen_com"],
            }

            batch.append(stat)

            # -- Flush batch when full ------------------------------------
            if len(batch) >= _BATCH_SIZE:
                n = _flush_batch(pg_cur, batch)
                total_inserted += n
                total_conflict += len(batch) - n
                batch = []

            # -- Progress report ------------------------------------------
            if total_processed % _LOG_INTERVAL == 0:
                logger.info(
                    "Progress: %d rows processed | inserted=%d conflict=%d "
                    "skipped_player=%d skipped_matchday=%d",
                    total_processed,
                    total_inserted,
                    total_conflict,
                    total_skipped_player,
                    total_skipped_matchday,
                )

        # -- Flush remaining rows -----------------------------------------
        if batch:
            n = _flush_batch(pg_cur, batch)
            total_inserted += n
            total_conflict += len(batch) - n

    mysql_cursor.close()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    logger.info("player_stats migration complete.")
    logger.info("  Total rows processed:  %d", total_processed)
    logger.info("  Rows inserted:         %d", total_inserted)
    logger.info("  Rows skipped (ON CONFLICT, already existed): %d", total_conflict)
    logger.info("  Rows skipped (player not in ctx.player_map):   %d", total_skipped_player)
    logger.info("  Rows skipped (matchday not in ctx.matchday_map): %d", total_skipped_matchday)
