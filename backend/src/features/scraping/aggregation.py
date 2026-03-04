from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ScoreAggregator:
    """Recalculates all fantasy scores for a matchday after player stats are updated.

    The aggregation runs four sequential UPDATE statements using raw SQL so that
    PostgreSQL's ``UPDATE ... FROM`` and window-function patterns are expressed
    naturally without fighting the ORM.

    Steps
    -----
    1. ``lineup_players.points`` ← ``player_stats.pts_total``
       (join through ``lineups.matchday_id`` and ``player_stats.matchday_id``).
    2. ``lineups.total_points`` ← ``SUM(lineup_players.points)``.
    3. ``participant_matchday_scores.total_points`` ← ``lineups.total_points``.
    4. ``participant_matchday_scores.ranking`` ← row-number ordered by
       ``total_points DESC``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def aggregate_matchday(self, matchday_id: int) -> None:
        """Run all four aggregation steps for *matchday_id*.

        Safe to call multiple times — every statement is idempotent.

        Parameters
        ----------
        matchday_id:
            Primary key of the ``matchdays`` row to aggregate.
        """
        logger.info("ScoreAggregator.aggregate_matchday: matchday_id=%d — start", matchday_id)

        await self._update_lineup_player_points(matchday_id)
        await self._update_lineup_totals(matchday_id)
        await self._update_participant_scores(matchday_id)
        await self._update_rankings(matchday_id)

        logger.info("ScoreAggregator.aggregate_matchday: matchday_id=%d — done", matchday_id)

    # ------------------------------------------------------------------
    # Private step implementations
    # ------------------------------------------------------------------

    async def _update_lineup_player_points(self, matchday_id: int) -> None:
        """Step 1: set each lineup_player.points = matching player_stat.pts_total."""
        sql = text(
            """
            UPDATE lineup_players lp
            SET    points = ps.pts_total
            FROM   lineups l,
                   player_stats ps
            WHERE  l.matchday_id   = :matchday_id
              AND  lp.lineup_id    = l.id
              AND  ps.player_id    = lp.player_id
              AND  ps.matchday_id  = :matchday_id
            """
        )
        result = await self.session.execute(sql, {"matchday_id": matchday_id})
        logger.debug(
            "_update_lineup_player_points: matchday_id=%d rows_affected=%d",
            matchday_id,
            result.rowcount,  # type: ignore[attr-defined]
        )

    async def _update_lineup_totals(self, matchday_id: int) -> None:
        """Step 2: recalculate lineups.total_points from sum of lineup_players.points."""
        sql = text(
            """
            UPDATE lineups
            SET    total_points = (
                       SELECT COALESCE(SUM(lp.points), 0)
                       FROM   lineup_players lp
                       WHERE  lp.lineup_id = lineups.id
                   )
            WHERE  matchday_id = :matchday_id
            """
        )
        result = await self.session.execute(sql, {"matchday_id": matchday_id})
        logger.debug(
            "_update_lineup_totals: matchday_id=%d rows_affected=%d",
            matchday_id,
            result.rowcount,  # type: ignore[attr-defined]
        )

    async def _update_participant_scores(self, matchday_id: int) -> None:
        """Step 3: copy lineups.total_points into participant_matchday_scores.total_points."""
        sql = text(
            """
            UPDATE participant_matchday_scores pms
            SET    total_points = l.total_points
            FROM   lineups l
            WHERE  l.matchday_id     = :matchday_id
              AND  l.participant_id  = pms.participant_id
              AND  pms.matchday_id   = :matchday_id
            """
        )
        result = await self.session.execute(sql, {"matchday_id": matchday_id})
        logger.debug(
            "_update_participant_scores: matchday_id=%d rows_affected=%d",
            matchday_id,
            result.rowcount,  # type: ignore[attr-defined]
        )

    async def _update_rankings(self, matchday_id: int) -> None:
        """Step 4: assign participant_matchday_scores.ranking via ROW_NUMBER window function."""
        sql = text(
            """
            UPDATE participant_matchday_scores
            SET    ranking = sub.rn
            FROM   (
                       SELECT id,
                              ROW_NUMBER() OVER (ORDER BY total_points DESC) AS rn
                       FROM   participant_matchday_scores
                       WHERE  matchday_id = :matchday_id
                   ) sub
            WHERE  participant_matchday_scores.id = sub.id
            """
        )
        result = await self.session.execute(sql, {"matchday_id": matchday_id})
        logger.debug(
            "_update_rankings: matchday_id=%d rows_affected=%d",
            matchday_id,
            result.rowcount,  # type: ignore[attr-defined]
        )
