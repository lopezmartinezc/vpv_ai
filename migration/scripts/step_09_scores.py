"""Step 09: Calculate participant_matchday_scores from PostgreSQL data."""

import logging

from context import MigrationContext

logger = logging.getLogger(__name__)


def run(mysql_conn, pg_conn, ctx: MigrationContext) -> None:
    pg_cur = pg_conn.cursor()

    # 1. Insert participant_matchday_scores: sum pts_total of each participant's
    #    lined-up players for each matchday, considering match.counts
    logger.info("Calculating participant matchday scores...")
    pg_cur.execute("""
        INSERT INTO participant_matchday_scores (participant_id, matchday_id, total_points)
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
        GROUP BY l.participant_id, l.matchday_id
        ON CONFLICT (participant_id, matchday_id) DO UPDATE
            SET total_points = EXCLUDED.total_points
    """)
    scores_count = pg_cur.rowcount
    logger.info("  Inserted/updated %d participant_matchday_scores", scores_count)

    # 2. Calculate rankings per matchday
    logger.info("Calculating rankings per matchday...")
    pg_cur.execute("""
        UPDATE participant_matchday_scores pms
        SET ranking = sub.rnk
        FROM (
            SELECT id,
                   RANK() OVER (
                       PARTITION BY matchday_id
                       ORDER BY total_points DESC
                   )::SMALLINT AS rnk
            FROM participant_matchday_scores
        ) sub
        WHERE pms.id = sub.id
    """)
    logger.info("  Updated rankings for %d rows", pg_cur.rowcount)

    pg_cur.close()
    logger.info("Step 09 complete: participant_matchday_scores calculated")
