"""
step_05_matchdays.py - Migrate matchdays and matches.

MySQL source table: list_jornadas_temp
    eq_local    VARCHAR(40)   PK  -- home team display name
    eq_vis      VARCHAR(40)   PK  -- away team display name
    temporada   VARCHAR(14)   PK  -- season name
    jornada     TINYINT           -- matchday number
    resultado   VARCHAR(100)      -- score string, e.g. '2-1' / '2 - 1' / NULL
    contabiliza TINYINT DEFAULT 1 -- 1 = match counts towards fantasy scoring
    est_ok      TINYINT DEFAULT 0 -- 1 = statistics have been collected
    id_part     INT               -- source match identifier
    url_part    VARCHAR(200)      -- source match URL

PostgreSQL target table: matchdays
    id              SERIAL PK
    season_id       INT FK -> seasons.id
    number          SMALLINT
    status          VARCHAR(20)  DEFAULT 'pending'
    counts          BOOLEAN      DEFAULT TRUE
    first_match_at  TIMESTAMPTZ
    deadline_at     TIMESTAMPTZ
    stats_ok        BOOLEAN      DEFAULT FALSE
    UNIQUE(season_id, number)

PostgreSQL target table: matches
    id              SERIAL PK
    matchday_id     INT FK -> matchdays.id
    home_team_id    INT FK -> teams.id
    away_team_id    INT FK -> teams.id
    home_score      SMALLINT
    away_score      SMALLINT
    result          VARCHAR(100)
    counts          BOOLEAN      DEFAULT TRUE
    stats_ok        BOOLEAN      DEFAULT FALSE
    source_id       INT
    source_url      VARCHAR(200)
    played_at       TIMESTAMPTZ
    UNIQUE(matchday_id, home_team_id, away_team_id)

After insertion:
    ctx.matchday_map[(temporada, jornada_num)] = matchday_id
    ctx.match_map[(temporada, eq_local, eq_vis)]  = match_id
    ctx.match_team_lookup[(matchday_id, home_team_id)] = match_id
    ctx.match_team_lookup[(matchday_id, away_team_id)] = match_id
"""

import logging
import re

import mysql.connector
import psycopg

from context import MigrationContext

log = logging.getLogger(__name__)

# Pre-compiled pattern for score parsing: accepts '2-1', '2 - 1', '2 -1', etc.
_SCORE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_score(resultado: str | None) -> tuple[int | None, int | None]:
    """Parse a score string into (home_score, away_score).

    Handles None, empty string, and formats like '2-1' or '2 - 1'.
    Returns (None, None) when the result is missing or unparseable.
    """
    if not resultado:
        return None, None
    m = _SCORE_RE.match(resultado)
    if m:
        return int(m.group(1)), int(m.group(2))
    log.debug("Could not parse score string: %r", resultado)
    return None, None


# ---------------------------------------------------------------------------
# Step A: matchdays
# ---------------------------------------------------------------------------

def _migrate_matchdays(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> dict[str, int]:
    """Create one matchdays row per (temporada, jornada) pair.

    Returns a per-season count dict {temporada: num_matchdays_inserted}.
    """

    mysql_cur = mysql_conn.cursor(dictionary=True)
    mysql_cur.execute(
        """
        SELECT
            temporada,
            jornada,
            MAX(contabiliza) AS max_counts,
            MIN(est_ok)      AS min_est_ok
        FROM list_jornadas_temp
        GROUP BY temporada, jornada
        ORDER BY temporada, jornada
        """
    )
    groups = mysql_cur.fetchall()
    mysql_cur.close()

    log.info("Found %d (season, matchday) group(s) in list_jornadas_temp.", len(groups))

    # Load season matchday ranges from PG to apply matchday_start/matchday_end logic
    season_ranges: dict[int, tuple[int, int | None]] = {}
    with pg_conn.cursor() as pg_cur:
        pg_cur.execute("SELECT id, matchday_start, matchday_end FROM seasons")
        for r in pg_cur.fetchall():
            season_ranges[r[0]] = (r[1], r[2])

    insert_sql = """
        INSERT INTO matchdays (
            season_id,
            number,
            status,
            counts,
            stats_ok
        ) VALUES (
            %(season_id)s,
            %(number)s,
            %(status)s,
            %(counts)s,
            %(stats_ok)s
        )
        RETURNING id
    """

    total_inserted = 0
    skipped_no_season = 0
    per_season_counts: dict[str, int] = {}

    with pg_conn.cursor() as pg_cur:
        for row in groups:
            temporada: str = row["temporada"]
            jornada: int = int(row["jornada"])

            season_id = ctx.season_map.get(temporada)
            if season_id is None:
                log.warning(
                    "Season '%s' not found in ctx.season_map — skipping matchday %d.",
                    temporada,
                    jornada,
                )
                skipped_no_season += 1
                continue

            # matchday.counts = TRUE if at least one match in the matchday counts
            # (MAX(contabiliza) > 0) AND the matchday is within the season range.
            counts: bool = (row["max_counts"] or 0) > 0
            md_start, md_end = season_ranges.get(season_id, (1, None))
            if jornada < md_start:
                counts = False
            if md_end is not None and jornada > md_end:
                counts = False

            # matchday.stats_ok = TRUE only when ALL matches have statistics
            # (MIN(est_ok) > 0).
            stats_ok: bool = (row["min_est_ok"] or 0) > 0

            params = {
                "season_id": season_id,
                "number": jornada,
                "status": "completed",   # all source data is historical
                "counts": counts,
                "stats_ok": stats_ok,
            }

            pg_cur.execute(insert_sql, params)
            (matchday_id,) = pg_cur.fetchone()

            ctx.matchday_map[(temporada, jornada)] = matchday_id

            per_season_counts[temporada] = per_season_counts.get(temporada, 0) + 1
            total_inserted += 1

    if skipped_no_season:
        log.warning(
            "Matchdays skipped (season not in ctx.season_map): %d", skipped_no_season
        )

    return per_season_counts


# ---------------------------------------------------------------------------
# Step B: matches
# ---------------------------------------------------------------------------

def _migrate_matches(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> dict[str, int]:
    """Create one matches row per row in list_jornadas_temp.

    Returns a per-season count dict {temporada: num_matches_inserted}.
    """

    mysql_cur = mysql_conn.cursor(dictionary=True)
    mysql_cur.execute(
        """
        SELECT
            temporada,
            jornada,
            TRIM(eq_local)  AS eq_local,
            TRIM(eq_vis)    AS eq_vis,
            resultado,
            contabiliza,
            est_ok,
            id_part,
            url_part
        FROM list_jornadas_temp
        ORDER BY temporada, jornada, eq_local, eq_vis
        """
    )
    match_rows = mysql_cur.fetchall()
    mysql_cur.close()

    log.info("Found %d match row(s) in list_jornadas_temp.", len(match_rows))

    insert_sql = """
        INSERT INTO matches (
            matchday_id,
            home_team_id,
            away_team_id,
            home_score,
            away_score,
            result,
            counts,
            stats_ok,
            source_id,
            source_url
        ) VALUES (
            %(matchday_id)s,
            %(home_team_id)s,
            %(away_team_id)s,
            %(home_score)s,
            %(away_score)s,
            %(result)s,
            %(counts)s,
            %(stats_ok)s,
            %(source_id)s,
            %(source_url)s
        )
        RETURNING id
    """

    total_inserted = 0
    skipped_no_matchday = 0
    skipped_no_team = 0
    per_season_counts: dict[str, int] = {}

    with pg_conn.cursor() as pg_cur:
        for row in match_rows:
            temporada: str = row["temporada"]
            jornada: int = int(row["jornada"])
            eq_local: str = row["eq_local"]
            eq_vis: str = row["eq_vis"]

            # -- Resolve matchday -------------------------------------------
            matchday_id = ctx.matchday_map.get((temporada, jornada))
            if matchday_id is None:
                log.warning(
                    "Matchday not found for season '%s' jornada %d — "
                    "skipping match '%s' vs '%s'.",
                    temporada,
                    jornada,
                    eq_local,
                    eq_vis,
                )
                skipped_no_matchday += 1
                continue

            # -- Resolve team ids -------------------------------------------
            home_team_id = ctx.team_map.get((temporada, eq_local))
            away_team_id = ctx.team_map.get((temporada, eq_vis))

            if home_team_id is None:
                log.warning(
                    "Home team '%s' not found in ctx.team_map for season '%s' — "
                    "skipping match vs '%s' (matchday %d).",
                    eq_local,
                    temporada,
                    eq_vis,
                    jornada,
                )
                skipped_no_team += 1
                continue

            if away_team_id is None:
                log.warning(
                    "Away team '%s' not found in ctx.team_map for season '%s' — "
                    "skipping match '%s' vs (matchday %d).",
                    eq_vis,
                    temporada,
                    eq_local,
                    jornada,
                )
                skipped_no_team += 1
                continue

            # -- Parse score ------------------------------------------------
            home_score, away_score = _parse_score(row["resultado"])

            params = {
                "matchday_id": matchday_id,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "result": row["resultado"],
                "counts": bool(row["contabiliza"]),
                "stats_ok": bool(row["est_ok"]),
                "source_id": row["id_part"],
                "source_url": row["url_part"],
            }

            pg_cur.execute(insert_sql, params)
            (match_id,) = pg_cur.fetchone()

            # -- Populate context maps --------------------------------------
            ctx.match_map[(temporada, eq_local, eq_vis)] = match_id

            # Reverse lookup used by later player-stats step.
            ctx.match_team_lookup[(matchday_id, home_team_id)] = match_id
            ctx.match_team_lookup[(matchday_id, away_team_id)] = match_id

            per_season_counts[temporada] = per_season_counts.get(temporada, 0) + 1
            total_inserted += 1

    if skipped_no_matchday:
        log.warning("Matches skipped (matchday not found): %d", skipped_no_matchday)

    if skipped_no_team:
        log.warning("Matches skipped (team not found in ctx.team_map): %d", skipped_no_team)

    return per_season_counts


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Migrate list_jornadas_temp into matchdays and matches."""

    # ---- Step A: matchdays ------------------------------------------------
    log.info("--- Step A: Creating matchdays ---")
    md_per_season = _migrate_matchdays(mysql_conn, pg_conn, ctx)

    total_matchdays = sum(md_per_season.values())
    for season_name in sorted(md_per_season):
        log.info(
            "  Season %-12s  matchdays inserted: %d",
            season_name,
            md_per_season[season_name],
        )
    log.info("Matchdays inserted total: %d", total_matchdays)
    log.info(
        "ctx.matchday_map populated with %d entries.", len(ctx.matchday_map)
    )

    # ---- Step B: matches --------------------------------------------------
    log.info("--- Step B: Creating matches ---")
    m_per_season = _migrate_matches(mysql_conn, pg_conn, ctx)

    total_matches = sum(m_per_season.values())
    for season_name in sorted(m_per_season):
        log.info(
            "  Season %-12s  matches inserted: %d",
            season_name,
            m_per_season[season_name],
        )
    log.info("Matches inserted total: %d", total_matches)
    log.info("ctx.match_map populated with %d entries.", len(ctx.match_map))
    log.info(
        "ctx.match_team_lookup populated with %d entries.",
        len(ctx.match_team_lookup),
    )
