from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.achievements.engine import AchievementEngine
from src.features.achievements.models import AchievementDefinition
from src.features.achievements.repository import AchievementRepository
from src.features.achievements.schemas import (
    AchievementDefinitionResponse,
    AchievementEntry,
    EvaluationResult,
    SeasonAchievementsResponse,
)
from src.features.seasons.repository import SeasonRepository

logger = logging.getLogger(__name__)


class AchievementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AchievementRepository(session)
        self.season_repo = SeasonRepository(session)
        self.engine = AchievementEngine(session)

    def _row_to_entry(self, row: dict) -> AchievementEntry:
        return AchievementEntry(
            id=row["id"],
            achievement_key=row["achievement_key"],
            name=row["name"],
            description=row["description"],
            icon=row["icon"],
            category=row["category"],
            tier=int(row["tier"]),
            participant_id=row["participant_id"],
            display_name=row["display_name"],
            matchday_number=row.get("matchday_number"),
            metadata=row.get("metadata"),
            created_at=row["created_at"],
        )

    async def get_definitions(self) -> list[AchievementDefinitionResponse]:
        defs: list[AchievementDefinition] = await self.repo.get_definitions()
        return [
            AchievementDefinitionResponse(
                id=d.id,
                achievement_key=d.achievement_key,
                name=d.name_es,
                description=d.description_es,
                category=d.category,
                icon=d.icon,
                max_tier=d.max_tier,
                repeatable=d.repeatable,
            )
            for d in defs
        ]

    async def get_season_achievements(self, season_id: int) -> SeasonAchievementsResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        rows = await self.repo.get_by_season(season_id)
        return SeasonAchievementsResponse(
            season_id=season_id,
            achievements=[self._row_to_entry(r) for r in rows],
        )

    async def get_participant_achievements(
        self, season_id: int, participant_id: int
    ) -> SeasonAchievementsResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        rows = await self.repo.get_by_participant(season_id, participant_id)
        return SeasonAchievementsResponse(
            season_id=season_id,
            achievements=[self._row_to_entry(r) for r in rows],
        )

    async def evaluate_matchday(self, season_id: int, matchday_number: int) -> EvaluationResult:
        """Evaluate achievements for a single matchday by number.

        Resolves the matchday_id from season_id + matchday_number.
        """
        from sqlalchemy import select

        from src.shared.models.matchday import Matchday

        stmt = select(Matchday).where(
            Matchday.season_id == season_id,
            Matchday.number == matchday_number,
        )
        result = await self.session.execute(stmt)
        matchday = result.scalar_one_or_none()
        if matchday is None:
            raise NotFoundError("Matchday", matchday_number)

        summary = await self.engine.evaluate_matchday(season_id, matchday.id, matchday_number)
        await self.session.commit()

        return EvaluationResult(
            matchday_number=matchday_number,
            evaluated=summary["evaluated"],
            granted=summary["granted"],
        )

    async def evaluate_all_matchdays(self, season_id: int) -> list[EvaluationResult]:
        """Evaluate achievements for all finished counting matchdays in a season."""
        from sqlalchemy import select

        from src.shared.models.matchday import Matchday

        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        # Clear existing achievements before full re-evaluation
        await self.repo.delete_season_achievements(season_id)

        stmt = (
            select(Matchday)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                Matchday.stats_ok.is_(True),
            )
            .order_by(Matchday.number)
        )
        result = await self.session.execute(stmt)
        matchdays = list(result.scalars().all())

        results = []
        for md in matchdays:
            summary = await self.engine.evaluate_matchday(season_id, md.id, md.number)
            results.append(
                EvaluationResult(
                    matchday_number=md.number,
                    evaluated=summary["evaluated"],
                    granted=summary["granted"],
                )
            )

        await self.session.commit()
        logger.info(
            "evaluate_all_matchdays: season_id=%d processed=%d matchdays",
            season_id,
            len(results),
        )
        return results
