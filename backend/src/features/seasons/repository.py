from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.base.repository import BaseRepository
from src.shared.models.season import ScoringRule, Season, SeasonPayment, ValidFormation


class SeasonRepository(BaseRepository[Season]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Season, session)

    async def get_current(self) -> Season | None:
        stmt = (
            select(Season)
            .where(Season.status == "active")
            .order_by(Season.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        season = result.scalar_one_or_none()
        if season is None:
            stmt = select(Season).order_by(Season.id.desc()).limit(1)
            result = await self.session.execute(stmt)
            season = result.scalar_one_or_none()
        return season

    async def get_scoring_rules(self, season_id: int) -> list[ScoringRule]:
        stmt = (
            select(ScoringRule)
            .where(ScoringRule.season_id == season_id)
            .order_by(ScoringRule.rule_key, ScoringRule.position)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_payments(self, season_id: int) -> list[SeasonPayment]:
        stmt = (
            select(SeasonPayment)
            .where(SeasonPayment.season_id == season_id)
            .order_by(SeasonPayment.payment_type, SeasonPayment.position_rank)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_valid_formations(self) -> list[ValidFormation]:
        stmt = select(ValidFormation).order_by(ValidFormation.formation)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
