"""
step_01_seasons.py - Migrate temporadas -> seasons.

MySQL source table: temporadas
    temporada         VARCHAR(15)  PK
    jornada_inicial   TINYINT
    jornada_actual    TINYINT
    jornada_cambios   TINYINT
    total_user        TINYINT
    jornada_escaneada TINYINT

PostgreSQL target table: seasons
    id                  SERIAL PK
    name                VARCHAR(15)   NOT NULL UNIQUE
    status              VARCHAR(20)   NOT NULL DEFAULT 'setup'
    matchday_start      SMALLINT      NOT NULL
    matchday_end        SMALLINT
    matchday_current    SMALLINT      NOT NULL DEFAULT 0
    matchday_winter     SMALLINT
    matchday_scanned    SMALLINT      NOT NULL DEFAULT 0
    draft_pool_size     SMALLINT      NOT NULL DEFAULT 26
    lineup_deadline_min SMALLINT      NOT NULL DEFAULT 30
    total_participants  SMALLINT      NOT NULL DEFAULT 0
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()

After insertion, ctx.season_map[name] = season_id is populated.
"""

import logging

import mysql.connector
import psycopg

from context import MigrationContext

log = logging.getLogger(__name__)

_ACTIVE_SEASON = "2025-2026"
_MATCHDAY_END = 38
_DRAFT_POOL_SIZE = 26
_LINEUP_DEADLINE_MIN = 30


def run(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Migrate all rows from temporadas into seasons."""

    # ------------------------------------------------------------------
    # Read source data from MySQL
    # ------------------------------------------------------------------
    mysql_cur = mysql_conn.cursor(dictionary=True)
    mysql_cur.execute(
        """
        SELECT
            temporada,
            jornada_inicial,
            jornada_actual,
            jornada_cambios,
            total_user,
            jornada_escaneada
        FROM temporadas
        ORDER BY temporada
        """
    )
    rows = mysql_cur.fetchall()
    mysql_cur.close()

    log.info("Found %d season(s) in MySQL temporadas.", len(rows))

    if not rows:
        log.warning("No seasons found in MySQL — nothing to migrate.")
        return

    # ------------------------------------------------------------------
    # Insert into PostgreSQL seasons
    # ------------------------------------------------------------------
    insert_sql = """
        INSERT INTO seasons (
            name,
            status,
            matchday_start,
            matchday_end,
            matchday_current,
            matchday_winter,
            matchday_scanned,
            draft_pool_size,
            lineup_deadline_min,
            total_participants
        ) VALUES (
            %(name)s,
            %(status)s,
            %(matchday_start)s,
            %(matchday_end)s,
            %(matchday_current)s,
            %(matchday_winter)s,
            %(matchday_scanned)s,
            %(draft_pool_size)s,
            %(lineup_deadline_min)s,
            %(total_participants)s
        )
        RETURNING id
    """

    inserted = 0

    with pg_conn.cursor() as pg_cur:
        for row in rows:
            name: str = row["temporada"]
            status = "active" if name == _ACTIVE_SEASON else "finished"

            params = {
                "name": name,
                "status": status,
                "matchday_start": row["jornada_inicial"],
                "matchday_end": _MATCHDAY_END,
                "matchday_current": row["jornada_actual"],
                "matchday_winter": row["jornada_cambios"],
                "matchday_scanned": row["jornada_escaneada"],
                "draft_pool_size": _DRAFT_POOL_SIZE,
                "lineup_deadline_min": _LINEUP_DEADLINE_MIN,
                "total_participants": row["total_user"],
            }

            pg_cur.execute(insert_sql, params)
            (season_id,) = pg_cur.fetchone()

            ctx.season_map[name] = season_id
            inserted += 1

            log.info(
                "  Inserted season %-12s  status=%-8s  id=%d",
                name,
                status,
                season_id,
            )

    log.info("Seasons inserted: %d", inserted)
    log.info("ctx.season_map populated with %d entries.", len(ctx.season_map))
