"""
step_06_players.py - Migrate unique players per season from jornadas_temp -> players.

MySQL source table: jornadas_temp (relevant columns)
    nom_url    VARCHAR(200)  -- player slug / URL identifier
    jornada    SMALLINT      -- matchday number
    temporada  VARCHAR(15)   -- season name
    equipo     VARCHAR(100)  -- team display name (may need TRIM)
    pos        VARCHAR(3)    -- position: POR / DEF / MED / DEL
    nom_hum    VARCHAR(200)  -- human-readable display name
    id_user    SMALLINT      -- 0 or NULL means unowned; >0 = slot id of owner

PostgreSQL target table: players
    id           SERIAL PK
    season_id    INT FK  -> seasons.id
    team_id      INT FK  -> teams.id
    name         VARCHAR(200)
    display_name VARCHAR(200)
    slug         VARCHAR(200)
    position     VARCHAR(3)
    photo_path   VARCHAR(255)
    source_url   VARCHAR(500)
    is_available BOOLEAN  DEFAULT TRUE
    owner_id     INT FK nullable -> season_participants.id
    UNIQUE(season_id, slug)

Algorithm:
    For each player per season we take values from their LAST matchday, because
    position and team can change mid-season.  A self-join on (nom_url, temporada,
    MAX(jornada)) gives us one canonical row per player-season.

    Players whose team is not in ctx.team_map are foreign/cup players and are
    skipped.  For owned players the owner is resolved from ctx.participant_map.

After insertion ctx.player_map[(temporada, nom_url)] = player_id is populated.
"""

import logging

import mysql.connector
import psycopg

from context import MigrationContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_MYSQL_QUERY = """
SELECT
    j.nom_url,
    j.temporada,
    TRIM(j.equipo) AS equipo,
    j.pos,
    j.nom_hum,
    j.id_user
FROM jornadas_temp j
INNER JOIN (
    SELECT nom_url, temporada, MAX(jornada) AS max_jornada
    FROM jornadas_temp
    GROUP BY nom_url, temporada
) latest
    ON  j.nom_url   = latest.nom_url
    AND j.temporada = latest.temporada
    AND j.jornada   = latest.max_jornada
ORDER BY j.temporada, j.nom_url
"""

_INSERT_PLAYER = """
INSERT INTO players (
    season_id,
    team_id,
    name,
    display_name,
    slug,
    position,
    photo_path,
    source_url,
    is_available,
    owner_id
)
VALUES (
    %(season_id)s,
    %(team_id)s,
    %(name)s,
    %(display_name)s,
    %(slug)s,
    %(position)s,
    %(photo_path)s,
    %(source_url)s,
    %(is_available)s,
    %(owner_id)s
)
ON CONFLICT (season_id, slug) DO NOTHING
RETURNING id
"""


# ---------------------------------------------------------------------------
# Main step
# ---------------------------------------------------------------------------

def run(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Migrate unique players per season from jornadas_temp into players."""

    # ------------------------------------------------------------------
    # 1. Read source data from MySQL (one canonical row per player-season)
    # ------------------------------------------------------------------
    mysql_cur = mysql_conn.cursor(dictionary=True)
    mysql_cur.execute(_MYSQL_QUERY)
    rows = mysql_cur.fetchall()
    mysql_cur.close()

    logger.info("Found %d unique player-season row(s) from jornadas_temp.", len(rows))

    if not rows:
        logger.warning("No player rows found in MySQL — nothing to migrate.")
        return

    # ------------------------------------------------------------------
    # 2. Insert into PostgreSQL players
    # ------------------------------------------------------------------
    total_inserted = 0
    total_skipped_team = 0
    total_skipped_season = 0
    total_conflict = 0
    per_season_counts: dict[str, int] = {}
    skipped_teams: dict[str, set[str]] = {}  # temporada -> set of team names

    with pg_conn.cursor() as pg_cur:
        for row in rows:
            nom_url: str = row["nom_url"]
            temporada: str = row["temporada"]
            equipo: str = row["equipo"] or ""
            pos: str | None = row["pos"]
            nom_hum: str | None = row["nom_hum"]
            id_user: int | None = row["id_user"]

            # -- Resolve season_id ----------------------------------------
            season_id = ctx.season_map.get(temporada)
            if season_id is None:
                logger.warning(
                    "Season '%s' not found in ctx.season_map — skipping player '%s'.",
                    temporada,
                    nom_url,
                )
                total_skipped_season += 1
                continue

            # -- Filter: skip players from foreign / cup teams -------------
            team_id = ctx.team_map.get((temporada, equipo))
            if team_id is None:
                logger.debug(
                    "Team '%s' not in ctx.team_map for season '%s' — skipping player '%s'.",
                    equipo,
                    temporada,
                    nom_url,
                )
                skipped_teams.setdefault(temporada, set()).add(equipo)
                total_skipped_team += 1
                continue

            # -- Resolve owner_id -----------------------------------------
            owner_id: int | None = None
            if id_user and id_user > 0:
                owner_id = ctx.participant_map.get((temporada, id_user))
                if owner_id is None:
                    logger.warning(
                        "id_user=%d not found in ctx.participant_map for season '%s' "
                        "(player '%s') — treating as unowned.",
                        id_user,
                        temporada,
                        nom_url,
                    )

            is_available: bool = owner_id is None

            params = {
                "season_id": season_id,
                "team_id": team_id,
                "name": nom_hum or nom_url,
                "display_name": nom_hum or nom_url,
                "slug": nom_url,
                "position": pos,
                "photo_path": None,
                "source_url": None,
                "is_available": is_available,
                "owner_id": owner_id,
            }

            pg_cur.execute(_INSERT_PLAYER, params)
            result = pg_cur.fetchone()

            if result is None:
                # ON CONFLICT DO NOTHING — row already existed
                logger.debug(
                    "Player '%s' in season '%s' already exists — skipped (conflict).",
                    nom_url,
                    temporada,
                )
                total_conflict += 1
                # Still populate the map by querying the existing id
                pg_cur.execute(
                    "SELECT id FROM players WHERE season_id = %s AND slug = %s",
                    (season_id, nom_url),
                )
                existing = pg_cur.fetchone()
                if existing:
                    ctx.player_map[(temporada, nom_url)] = existing[0]
                continue

            (player_id,) = result
            ctx.player_map[(temporada, nom_url)] = player_id

            per_season_counts[temporada] = per_season_counts.get(temporada, 0) + 1
            total_inserted += 1

    # ------------------------------------------------------------------
    # 3. Summary logging
    # ------------------------------------------------------------------
    for season_name in sorted(per_season_counts):
        logger.info(
            "  Season %-12s  players inserted: %d",
            season_name,
            per_season_counts[season_name],
        )

    logger.info("Players inserted total:   %d", total_inserted)
    logger.info("Players skipped (ON CONFLICT, already existed): %d", total_conflict)

    if total_skipped_team:
        logger.info(
            "Players skipped (team not in La Liga schedule): %d", total_skipped_team
        )
        for temporada in sorted(skipped_teams):
            teams_list = sorted(skipped_teams[temporada])
            logger.info(
                "  Season '%s' — %d foreign team(s): %s",
                temporada,
                len(teams_list),
                ", ".join(teams_list),
            )

    if total_skipped_season:
        logger.warning(
            "Players skipped (season not in ctx.season_map): %d", total_skipped_season
        )

    logger.info(
        "ctx.player_map populated with %d entries.", len(ctx.player_map)
    )
