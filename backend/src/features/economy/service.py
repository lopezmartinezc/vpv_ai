from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.economy.repository import EconomyRepository
from src.features.economy.schemas import (
    EconomyResponse,
    ParticipantBalance,
    ParticipantEconomyResponse,
    TransactionEntry,
)
from src.features.seasons.repository import SeasonRepository


class EconomyService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = EconomyRepository(session)
        self.season_repo = SeasonRepository(session)

    async def get_overview(self, season_id: int) -> EconomyResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        rows = await self.repo.get_balances(season_id)
        return EconomyResponse(
            season_id=season_id,
            balances=[
                ParticipantBalance(
                    participant_id=r.participant_id,
                    display_name=r.display_name,
                    initial_fee=float(r.initial_fee),
                    weekly_total=float(r.weekly_total),
                    draft_fees=float(r.draft_fees),
                    net_balance=float(r.net_balance),
                )
                for r in rows
            ],
        )

    async def get_participant_transactions(
        self, season_id: int, participant_id: int,
    ) -> ParticipantEconomyResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        display_name = await self.repo.get_participant_display_name(participant_id)
        if display_name is None:
            raise NotFoundError("Participant", participant_id)

        tx_rows = await self.repo.get_transactions(season_id, participant_id)
        net_balance = await self.repo.get_participant_net_balance(
            season_id, participant_id,
        )

        return ParticipantEconomyResponse(
            participant_id=participant_id,
            display_name=display_name,
            net_balance=float(net_balance),
            transactions=[
                TransactionEntry(
                    id=t.id,
                    type=t.type,
                    amount=float(t.amount),
                    description=t.description,
                    matchday_number=t.matchday_number,
                    created_at=t.created_at,
                )
                for t in tx_rows
            ],
        )
