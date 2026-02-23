from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.seasons.repository import SeasonRepository
from src.shared.models.season import ScoringRule, Season, SeasonPayment, ValidFormation


class SeasonService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = SeasonRepository(session)

    async def list_seasons(self) -> list[Season]:
        return await self.repo.list(order_by=Season.id.desc())

    async def get_season(self, season_id: int) -> Season:
        season = await self.repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)
        return season

    async def get_current_season(self) -> Season:
        season = await self.repo.get_current()
        if season is None:
            raise NotFoundError("Season", "current")
        return season

    async def get_scoring_rules(self, season_id: int) -> list[ScoringRule]:
        await self.get_season(season_id)
        return await self.repo.get_scoring_rules(season_id)

    async def get_payments(self, season_id: int) -> list[SeasonPayment]:
        await self.get_season(season_id)
        return await self.repo.get_payments(season_id)

    async def get_valid_formations(self) -> list[ValidFormation]:
        return await self.repo.get_valid_formations()
