"""
step_08_lineups.py - Migrate fantasy lineups from jornadas_temp -> lineups + lineup_players.

Source:
    jornadas_temp WHERE alineado = 1 AND id_user > 0
    (alineaciones_temp has alineado=0 for all rows — it is roster/pool data, NOT lineup data)

PostgreSQL target tables:

    lineups
        id              SERIAL PK
        participant_id  INT FK -> season_participants.id
        matchday_id     INT FK -> matchdays.id
        formation       VARCHAR(10)
        confirmed       BOOLEAN
        confirmed_at    TIMESTAMPTZ
        telegram_sent   BOOLEAN
        telegram_sent_at TIMESTAMPTZ
        image_path      VARCHAR(255)
        total_points    SMALLINT
        UNIQUE(participant_id, matchday_id)

    lineup_players
        id              SERIAL PK
        lineup_id       INT FK -> lineups.id
        player_id       INT FK -> players.id
        position_slot   VARCHAR(3)
        display_order   SMALLINT
        points          SMALLINT
        UNIQUE(lineup_id, player_id)
        UNIQUE(lineup_id, display_order)

Algorithm:
    1. Query jornadas_temp WHERE alineado = 1 AND id_user > 0,
       ordered so itertools.groupby can group by (temporada, jornada, id_user).
    2. For each group build one lineups row and N lineup_players rows.
    3. After all inserts, bulk-update points from player_stats and
       recompute lineups.total_points.
"""

import itertools
import logging
from collections import Counter

import mysql.connector
import psycopg

from context import MigrationContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MySQL query
# ---------------------------------------------------------------------------

_MYSQL_QUERY = """
SELECT
    nom_url,
    jornada,
    temporada,
    pos,
    id_user,
    order_astudillo
FROM jornadas_temp
WHERE alineado = 1
  AND id_user > 0
ORDER BY temporada, jornada, id_user, order_astudillo
"""

# ---------------------------------------------------------------------------
# PostgreSQL inserts
# ---------------------------------------------------------------------------

_INSERT_LINEUP = """
INSERT INTO lineups (
    participant_id,
    matchday_id,
    formation,
    confirmed,
    telegram_sent,
    total_points
)
VALUES (
    %(participant_id)s,
    %(matchday_id)s,
    %(formation)s,
    TRUE,
    FALSE,
    0
)
ON CONFLICT (participant_id, matchday_id) DO NOTHING
RETURNING id
"""

_INSERT_LINEUP_PLAYER = """
INSERT INTO lineup_players (
    lineup_id,
    player_id,
    position_slot,
    display_order,
    points
)
VALUES (
    %(lineup_id)s,
    %(player_id)s,
    %(position_slot)s,
    %(display_order)s,
    0
)
ON CONFLICT DO NOTHING
"""

# ---------------------------------------------------------------------------
# Bulk point updates (run once after all rows are inserted)
# ---------------------------------------------------------------------------

_UPDATE_LINEUP_PLAYER_POINTS = """
UPDATE lineup_players lp
SET points = COALESCE(ps.pts_total, 0)
FROM lineups l, player_stats ps
WHERE lp.lineup_id = l.id
  AND ps.player_id = lp.player_id
  AND ps.matchday_id = l.matchday_id
"""

_UPDATE_LINEUP_TOTAL_POINTS = """
UPDATE lineups l
SET total_points = sub.total
FROM (
    SELECT lineup_id, SUM(points) AS total
    FROM lineup_players
    GROUP BY lineup_id
) sub
WHERE l.id = sub.lineup_id
"""


# ---------------------------------------------------------------------------
# Helper: derive formation string
# ---------------------------------------------------------------------------

_FORMATION_POSITIONS = ("POR", "DEF", "MED", "DEL")


def _build_formation(players: list[dict]) -> str:
    """Return '{POR}-{DEF}-{MED}-{DEL}' based on position counts in the group."""
    counts: Counter[str] = Counter(p["pos"] for p in players if p["pos"])
    parts = [str(counts.get(pos, 0)) for pos in _FORMATION_POSITIONS]
    return "-".join(parts)


# ---------------------------------------------------------------------------
# Main step
# ---------------------------------------------------------------------------

def run(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Migrate fantasy lineups from jornadas_temp into lineups + lineup_players."""

    # ------------------------------------------------------------------
    # 1. Read lineup rows from MySQL (buffered — volume is much smaller
    #    than all of jornadas_temp; alineado=1 is a small subset)
    # ------------------------------------------------------------------
    mysql_cur = mysql_conn.cursor(dictionary=True)
    mysql_cur.execute(_MYSQL_QUERY)
    rows = mysql_cur.fetchall()
    mysql_cur.close()

    logger.info(
        "Found %d lineup player-row(s) in jornadas_temp (alineado=1, id_user>0).",
        len(rows),
    )

    if not rows:
        logger.warning("No lineup rows found — nothing to migrate.")
        return

    # ------------------------------------------------------------------
    # 2. Group by (temporada, jornada, id_user) and insert
    # ------------------------------------------------------------------
    lineups_inserted = 0
    lineups_conflict = 0
    lineup_players_inserted = 0
    lineup_players_skipped_player = 0
    lineup_players_skipped_matchday = 0
    lineup_players_skipped_participant = 0
    lineup_players_conflict = 0

    def _group_key(r: dict) -> tuple:
        return (r["temporada"], r["jornada"], r["id_user"])

    with pg_conn.cursor() as pg_cur:
        for group_key, group_iter in itertools.groupby(rows, key=_group_key):
            temporada, jornada, id_user = group_key
            group_players = list(group_iter)

            # -- Resolve participant_id -----------------------------------
            participant_id = ctx.participant_map.get((temporada, id_user))
            if participant_id is None:
                logger.warning(
                    "id_user=%d / season '%s' not in ctx.participant_map — "
                    "skipping lineup for jornada=%d.",
                    id_user,
                    temporada,
                    jornada,
                )
                lineup_players_skipped_participant += len(group_players)
                continue

            # -- Resolve matchday_id --------------------------------------
            matchday_id = ctx.matchday_map.get((temporada, jornada))
            if matchday_id is None:
                logger.warning(
                    "jornada=%d / season '%s' not in ctx.matchday_map — "
                    "skipping lineup for id_user=%d.",
                    jornada,
                    temporada,
                    id_user,
                )
                lineup_players_skipped_matchday += len(group_players)
                continue

            # -- Calculate formation --------------------------------------
            formation = _build_formation(group_players)

            # -- Insert lineup row ----------------------------------------
            pg_cur.execute(
                _INSERT_LINEUP,
                {
                    "participant_id": participant_id,
                    "matchday_id": matchday_id,
                    "formation": formation,
                },
            )
            result = pg_cur.fetchone()

            if result is None:
                # ON CONFLICT DO NOTHING — lineup already existed; fetch id
                logger.debug(
                    "Lineup already exists for participant_id=%d matchday_id=%d — "
                    "fetching existing id.",
                    participant_id,
                    matchday_id,
                )
                pg_cur.execute(
                    "SELECT id FROM lineups WHERE participant_id = %s AND matchday_id = %s",
                    (participant_id, matchday_id),
                )
                existing = pg_cur.fetchone()
                if existing is None:
                    logger.error(
                        "Could not find existing lineup for participant_id=%d matchday_id=%d "
                        "— skipping lineup_players for this group.",
                        participant_id,
                        matchday_id,
                    )
                    continue
                lineup_id = existing[0]
                lineups_conflict += 1
            else:
                (lineup_id,) = result
                lineups_inserted += 1

            # -- Insert lineup_players ------------------------------------
            for idx, player_row in enumerate(group_players):
                nom_url: str = player_row["nom_url"]
                pos: str | None = player_row["pos"]
                order_val = player_row["order_astudillo"]
                display_order: int = int(order_val) if order_val is not None else idx + 1

                player_id = ctx.player_map.get((temporada, nom_url))
                if player_id is None:
                    logger.debug(
                        "Player '%s' / season '%s' not in ctx.player_map — "
                        "skipping lineup_player entry.",
                        nom_url,
                        temporada,
                    )
                    lineup_players_skipped_player += 1
                    continue

                pg_cur.execute(
                    _INSERT_LINEUP_PLAYER,
                    {
                        "lineup_id": lineup_id,
                        "player_id": player_id,
                        "position_slot": pos,
                        "display_order": display_order,
                    },
                )
                if pg_cur.rowcount and pg_cur.rowcount > 0:
                    lineup_players_inserted += 1
                else:
                    lineup_players_conflict += 1

        # ------------------------------------------------------------------
        # 3. Bulk-update points from player_stats
        # ------------------------------------------------------------------
        logger.info("Updating lineup_players.points from player_stats...")
        pg_cur.execute(_UPDATE_LINEUP_PLAYER_POINTS)
        lp_updated = pg_cur.rowcount
        logger.info("  lineup_players rows updated with points: %d", lp_updated)

        logger.info("Updating lineups.total_points (SUM of lineup_players.points)...")
        pg_cur.execute(_UPDATE_LINEUP_TOTAL_POINTS)
        l_updated = pg_cur.rowcount
        logger.info("  lineups rows updated with total_points:  %d", l_updated)

    # ------------------------------------------------------------------
    # 4. Summary logging
    # ------------------------------------------------------------------
    logger.info("Lineups migration complete.")
    logger.info("  lineups inserted:          %d", lineups_inserted)
    logger.info("  lineups skipped (conflict): %d", lineups_conflict)
    logger.info("  lineup_players inserted:          %d", lineup_players_inserted)
    logger.info("  lineup_players skipped (conflict): %d", lineup_players_conflict)
    if lineup_players_skipped_player:
        logger.warning(
            "  lineup_players skipped (player not in ctx.player_map):      %d",
            lineup_players_skipped_player,
        )
    if lineup_players_skipped_matchday:
        logger.warning(
            "  lineup_players skipped (matchday not in ctx.matchday_map):  %d",
            lineup_players_skipped_matchday,
        )
    if lineup_players_skipped_participant:
        logger.warning(
            "  lineup_players skipped (participant not in ctx.participant_map): %d",
            lineup_players_skipped_participant,
        )
