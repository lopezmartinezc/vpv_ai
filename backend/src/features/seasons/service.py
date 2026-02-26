from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.seasons.repository import SeasonRepository
from src.features.seasons.schemas import SeasonDetail, ScoringRuleResponse
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

    # --- Admin methods ---

    async def update_season(
        self,
        season_id: int,
        **kwargs: object,
    ) -> SeasonDetail:
        valid_statuses = {"setup", "active", "finished"}
        status = kwargs.get("status")
        if status and status not in valid_statuses:
            raise BusinessRuleError(f"Estado invalido: {status}")

        season = await self.repo.update_season(season_id, **kwargs)
        if season is None:
            raise NotFoundError("Season", season_id)
        await self.repo.session.commit()
        return SeasonDetail.model_validate(season)

    async def update_scoring_rules(
        self,
        season_id: int,
        updates: list[tuple[int, Decimal]],
    ) -> list[ScoringRuleResponse]:
        await self.get_season(season_id)
        for rule_id, value in updates:
            result = await self.repo.update_scoring_rule(rule_id, value)
            if result is None:
                raise NotFoundError("ScoringRule", rule_id)
        await self.repo.session.commit()
        rules = await self.repo.get_scoring_rules(season_id)
        return [ScoringRuleResponse.model_validate(r) for r in rules]
