from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.base.repository import BaseRepository
from src.shared.models.matchday import Matchday
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

    async def update_season(self, season_id: int, **kwargs: object) -> Season | None:
        season = await self.session.get(Season, season_id)
        if season is None:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(season, key, value)
        return season

    async def sync_matchday_counts(self, season_id: int, matchday_start: int) -> int:
        """Set counts=false for matchdays before matchday_start, counts=true for the rest."""
        await self.session.execute(
            update(Matchday)
            .where(Matchday.season_id == season_id, Matchday.number < matchday_start)
            .values(counts=False)
        )
        result = await self.session.execute(
            update(Matchday)
            .where(Matchday.season_id == season_id, Matchday.number >= matchday_start)
            .values(counts=True)
        )
        return result.rowcount

    async def update_scoring_rule(self, rule_id: int, value: object) -> ScoringRule | None:
        rule = await self.session.get(ScoringRule, rule_id)
        if rule is None:
            return None
        rule.value = value  # type: ignore[assignment]
        return rule
