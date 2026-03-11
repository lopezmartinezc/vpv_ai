from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.base.repository import BaseRepository
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.season import ScoringRule, Season, SeasonPayment, ValidFormation
from src.shared.models.user import User


@dataclass
class ParticipantRow:
    id: int
    user_id: int
    display_name: str
    draft_order: int | None
    is_active: bool


class SeasonRepository(BaseRepository[Season]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Season, session)

    async def get_current(self) -> Season | None:
        stmt = select(Season).where(Season.status == "active").order_by(Season.id.desc()).limit(1)
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

    async def get_participants(self, season_id: int) -> list[ParticipantRow]:
        stmt = (
            select(
                SeasonParticipant.id,
                SeasonParticipant.user_id,
                User.display_name,
                SeasonParticipant.draft_order,
                SeasonParticipant.is_active,
            )
            .join(User, User.id == SeasonParticipant.user_id)
            .where(SeasonParticipant.season_id == season_id)
            .order_by(SeasonParticipant.draft_order.asc().nulls_last(), SeasonParticipant.id)
        )
        result = await self.session.execute(stmt)
        return [
            ParticipantRow(
                id=row.id,
                user_id=row.user_id,
                display_name=row.display_name,
                draft_order=row.draft_order,
                is_active=row.is_active,
            )
            for row in result.all()
        ]

    async def toggle_participant_active(self, participant_id: int) -> ParticipantRow | None:
        participant = await self.session.get(SeasonParticipant, participant_id)
        if participant is None:
            return None
        participant.is_active = not participant.is_active
        user = await self.session.get(User, participant.user_id)
        if user is None:
            return None
        return ParticipantRow(
            id=participant.id,
            user_id=participant.user_id,
            display_name=user.display_name,
            draft_order=participant.draft_order,
            is_active=participant.is_active,
        )

    async def update_season(self, season_id: int, **kwargs: object) -> Season | None:
        season = await self.session.get(Season, season_id)
        if season is None:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(season, key, value)
        return season

    async def sync_matchday_counts(
        self,
        season_id: int,
        matchday_start: int,
        matchday_end: int | None = None,
    ) -> list[int]:
        """Sync counts flags based on matchday_start/end and return changed matchday ids.

        Matchdays with ``number < matchday_start`` or ``number > matchday_end``
        get ``counts=False``; those in range get ``counts=True``.

        Returns the list of matchday primary-key ids whose ``counts`` value was
        actually flipped so the caller can trigger score re-aggregation.
        """
        from sqlalchemy import select as sa_select

        # Build the "in range" condition
        in_range = Matchday.number >= matchday_start
        if matchday_end is not None:
            in_range = and_(in_range, Matchday.number <= matchday_end)

        # Detect matchdays whose counts will flip
        will_become_false = sa_select(Matchday.id).where(
            Matchday.season_id == season_id,
            Matchday.counts.is_(True),
            ~in_range,
        )
        will_become_true = sa_select(Matchday.id).where(
            Matchday.season_id == season_id,
            Matchday.counts.is_(False),
            in_range,
        )
        r1 = await self.session.execute(will_become_false)
        r2 = await self.session.execute(will_become_true)
        changed_ids: list[int] = [row[0] for row in r1.all()] + [row[0] for row in r2.all()]

        # Bulk update: out of range → false
        await self.session.execute(
            update(Matchday).where(Matchday.season_id == season_id, ~in_range).values(counts=False)
        )
        # In range → true
        await self.session.execute(
            update(Matchday).where(Matchday.season_id == season_id, in_range).values(counts=True)
        )
        return changed_ids

    async def update_payment(self, payment_id: int, amount: object) -> SeasonPayment | None:
        payment = await self.session.get(SeasonPayment, payment_id)
        if payment is None:
            return None
        payment.amount = amount  # type: ignore[assignment]
        return payment

    async def update_scoring_rule(self, rule_id: int, value: object) -> ScoringRule | None:
        rule = await self.session.get(ScoringRule, rule_id)
        if rule is None:
            return None
        rule.value = value  # type: ignore[assignment]
        return rule
