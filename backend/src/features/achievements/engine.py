from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.achievements.evaluators import ALL_EVALUATORS
from src.features.achievements.repository import AchievementRepository

logger = logging.getLogger(__name__)


class AchievementEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AchievementRepository(session)

    async def evaluate_matchday(
        self,
        season_id: int,
        matchday_id: int,
        matchday_number: int,
    ) -> dict[str, int]:
        """Run all evaluators for a matchday and persist results.

        Returns a summary dict with ``evaluated`` and ``granted`` counts.
        Safe to re-run: duplicate achievements are silently ignored via
        the uq_achievement constraint.
        """
        all_achievements = []

        for evaluator in ALL_EVALUATORS:
            try:
                results = await evaluator(self.session, season_id, matchday_id, matchday_number)
                all_achievements.extend(results)
            except Exception:
                logger.exception(
                    "AchievementEngine: evaluator %s failed for season_id=%d matchday_id=%d",
                    evaluator.__name__,
                    season_id,
                    matchday_id,
                )

        inserted = await self.repo.upsert_achievements(all_achievements)

        logger.info(
            "AchievementEngine: season_id=%d matchday_id=%d evaluated=%d candidates=%d granted=%d",
            season_id,
            matchday_id,
            len(ALL_EVALUATORS),
            len(all_achievements),
            inserted,
        )

        return {
            "evaluated": len(ALL_EVALUATORS),
            "granted": inserted,
        }
