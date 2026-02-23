"""
step_04_teams.py - Migrate La Liga teams per season.

MySQL source tables:
    equipos
        nombre      VARCHAR(100)  PK   -- team display name
        nom_url     VARCHAR(100)       -- full URL, e.g.
                                       --   'https://www.futbolfantasy.com/laliga/equipos/alaves'

    jornadas_temp
        temporada   VARCHAR(15)        -- season name
        equipo      VARCHAR(100)       -- team display name (may need TRIM)
        ... (other columns not used here)

    list_jornadas_temp
        temporada   VARCHAR(14)  PK
        jornada     TINYINT      PK
        eq_local    VARCHAR(40)  PK
        eq_vis      VARCHAR(40)  PK
        ... (other columns not used here)

PostgreSQL target table: teams
    id          SERIAL PK
    season_id   INT FK  -> seasons.id
    name        VARCHAR(100)
    short_name  VARCHAR(10)
    slug        VARCHAR(100)
    logo_path   VARCHAR(255)
    UNIQUE(season_id, slug)

After insertion, ctx.team_map[(temporada, team_name_trimmed)] = team_id.

Filter strategy:
    Only teams that appear in list_jornadas_temp (the real La Liga match
    schedule) are considered La Liga teams for a given season.  Any team
    present in jornadas_temp but absent from list_jornadas_temp for that
    season is treated as a foreign/cup team and skipped.
"""

import logging
import unicodedata

import mysql.connector
import psycopg

from context import MigrationContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug_from_url(url: str) -> str | None:
    """Extract the last path segment from a full URL.

    Example:
        'https://www.futbolfantasy.com/laliga/equipos/alaves' -> 'alaves'
    Returns None when the URL is blank or malformed.
    """
    if not url:
        return None
    segment = url.rstrip("/").rsplit("/", 1)[-1].strip()
    return segment if segment else None


def _slug_from_name(name: str) -> str:
    """Generate a URL-safe slug from a team display name.

    Steps:
        1. Decompose Unicode characters (NFD) to separate base letters from
           combining diacritics (accents), then keep only ASCII characters.
        2. Lowercase.
        3. Replace spaces with hyphens.
        4. Collapse multiple hyphens into one.
    """
    nfd = unicodedata.normalize("NFD", name)
    ascii_name = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    slug = ascii_name.lower().replace(" ", "-")
    # Collapse multiple hyphens that may result from special characters.
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


# ---------------------------------------------------------------------------
# Main step
# ---------------------------------------------------------------------------

def run(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Migrate La Liga teams per season into the PostgreSQL teams table."""

    # ------------------------------------------------------------------
    # 1. Build global slug lookup from equipos
    # ------------------------------------------------------------------
    mysql_cur = mysql_conn.cursor(dictionary=True)

    mysql_cur.execute("SELECT nombre, nom_url FROM equipos")
    equipos_rows = mysql_cur.fetchall()

    # nombre -> slug
    slug_lookup: dict[str, str] = {}
    for row in equipos_rows:
        nombre: str = row["nombre"]
        url_slug = _slug_from_url(row["nom_url"] or "")
        slug_lookup[nombre] = url_slug if url_slug else _slug_from_name(nombre)

    log.info("Built slug lookup for %d team(s) from equipos.", len(slug_lookup))

    # ------------------------------------------------------------------
    # 2. Build the set of real La Liga teams per season from list_jornadas_temp.
    #    A team is "real" if it appears as eq_local or eq_vis in the schedule.
    # ------------------------------------------------------------------
    mysql_cur.execute(
        """
        SELECT DISTINCT temporada, TRIM(eq_local) AS team
        FROM list_jornadas_temp
        WHERE eq_local IS NOT NULL AND TRIM(eq_local) != ''
        UNION
        SELECT DISTINCT temporada, TRIM(eq_vis)   AS team
        FROM list_jornadas_temp
        WHERE eq_vis IS NOT NULL AND TRIM(eq_vis) != ''
        """
    )
    laliga_rows = mysql_cur.fetchall()

    # (temporada, team_name) -> True
    laliga_teams: set[tuple[str, str]] = {
        (r["temporada"], r["team"]) for r in laliga_rows
    }

    seasons_in_schedule: set[str] = {r["temporada"] for r in laliga_rows}
    log.info(
        "Found La Liga team presence in %d season(s) from list_jornadas_temp.",
        len(seasons_in_schedule),
    )

    # ------------------------------------------------------------------
    # 3. Get distinct teams per season from jornadas_temp
    # ------------------------------------------------------------------
    mysql_cur.execute(
        """
        SELECT DISTINCT
            temporada,
            TRIM(equipo) AS equipo
        FROM jornadas_temp
        WHERE equipo IS NOT NULL AND TRIM(equipo) != ''
        ORDER BY temporada, equipo
        """
    )
    jornadas_rows = mysql_cur.fetchall()
    mysql_cur.close()

    log.info(
        "Found %d distinct (season, team) pair(s) in jornadas_temp.",
        len(jornadas_rows),
    )

    # ------------------------------------------------------------------
    # 4. Insert teams into PostgreSQL
    # ------------------------------------------------------------------
    insert_sql = """
        INSERT INTO teams (season_id, name, short_name, slug, logo_path)
        VALUES (%(season_id)s, %(name)s, %(short_name)s, %(slug)s, %(logo_path)s)
        RETURNING id
    """

    total_inserted = 0
    skipped_foreign = 0
    skipped_no_season = 0
    per_season_counts: dict[str, int] = {}

    with pg_conn.cursor() as pg_cur:
        for row in jornadas_rows:
            temporada: str = row["temporada"]
            team_name: str = row["equipo"]

            # -- Resolve season_id ------------------------------------------
            season_id = ctx.season_map.get(temporada)
            if season_id is None:
                log.warning(
                    "Season '%s' not found in ctx.season_map — skipping team '%s'.",
                    temporada,
                    team_name,
                )
                skipped_no_season += 1
                continue

            # -- Filter: skip foreign / cup teams ---------------------------
            if (temporada, team_name) not in laliga_teams:
                log.debug(
                    "Skipping foreign/cup team '%s' for season '%s'.",
                    team_name,
                    temporada,
                )
                skipped_foreign += 1
                continue

            # -- Resolve slug -----------------------------------------------
            slug = slug_lookup.get(team_name) or _slug_from_name(team_name)

            params = {
                "season_id": season_id,
                "name": team_name,
                "short_name": None,   # not available in source data
                "slug": slug,
                "logo_path": None,    # not available in source data
            }

            pg_cur.execute(insert_sql, params)
            (team_id,) = pg_cur.fetchone()

            ctx.team_map[(temporada, team_name)] = team_id

            per_season_counts[temporada] = per_season_counts.get(temporada, 0) + 1
            total_inserted += 1

    # ------------------------------------------------------------------
    # 5. Summary logging
    # ------------------------------------------------------------------
    for season_name in sorted(per_season_counts):
        log.info(
            "  Season %-12s  teams inserted: %d",
            season_name,
            per_season_counts[season_name],
        )

    log.info("Teams inserted total: %d", total_inserted)

    if skipped_foreign:
        log.info("Teams skipped (foreign/cup, not in La Liga schedule): %d", skipped_foreign)

    if skipped_no_season:
        log.warning("Teams skipped (season not in ctx.season_map): %d", skipped_no_season)

    log.info("ctx.team_map populated with %d entries.", len(ctx.team_map))
