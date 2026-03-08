from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.economy.repository import EconomyRepository, MatchdayRankingRow
from src.features.economy.schemas import (
    EconomyResponse,
    ParticipantBalance,
    ParticipantEconomyResponse,
    TransactionEntry,
)
from src.features.seasons.repository import SeasonRepository

logger = logging.getLogger(__name__)


def compute_weekly_amounts(
    rankings: list[MatchdayRankingRow],
    rules: dict[int, Decimal],
) -> list[tuple[int, Decimal]]:
    """Compute weekly payment for each participant based on ranking position.

    Returns list of (participant_id, amount) pairs.
    ``rules`` maps position_rank -> amount from season_payments table.
    Positions not in rules default to 0 (no payment).
    Tie adjustment: from worst to best, same points = same (worse) payment.
    """
    n = len(rankings)
    if n == 0 or not rules:
        return []

    # Step 1: assign base amount by sequential position (1-based index),
    # NOT by ranking (which has gaps on ties, e.g. 1,2,3,3,5...)
    amounts: list[Decimal] = []
    for i, _row in enumerate(rankings):
        amounts.append(rules.get(i + 1, Decimal("0")))

    # Step 2: tie adjustment — iterate from worst to best
    # If two players have the same total_points, the better-ranked one
    # gets the same (higher) payment as the worse-ranked one.
    prev_points = rankings[-1].total_points
    prev_amount = amounts[-1]
    for i in range(n - 2, -1, -1):
        if rankings[i].total_points > prev_points:
            prev_points = rankings[i].total_points
            prev_amount = amounts[i]
        else:
            prev_points = rankings[i].total_points
            amounts[i] = prev_amount

    return [
        (rankings[i].participant_id, amounts[i]) for i in range(n)
    ]


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
        self,
        season_id: int,
        participant_id: int,
    ) -> ParticipantEconomyResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        display_name = await self.repo.get_participant_display_name(participant_id)
        if display_name is None:
            raise NotFoundError("Participant", participant_id)

        tx_rows = await self.repo.get_transactions(season_id, participant_id)
        net_balance = await self.repo.get_participant_net_balance(
            season_id,
            participant_id,
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

    # --- Admin methods ---

    async def create_transaction(
        self,
        season_id: int,
        participant_id: int,
        tx_type: str,
        amount: float,
        description: str | None = None,
        matchday_id: int | None = None,
    ) -> TransactionEntry:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        valid_types = {
            "initial_fee",
            "weekly_payment",
            "winter_draft_fee",
            "prize",
            "manual_adjustment",
            "penalty",
        }
        if tx_type not in valid_types:
            raise BusinessRuleError(f"Tipo de transaccion invalido: {tx_type}")

        tx = await self.repo.create_transaction(
            season_id=season_id,
            participant_id=participant_id,
            tx_type=tx_type,
            amount=Decimal(str(amount)),
            description=description,
            matchday_id=matchday_id,
        )
        await self.repo.session.commit()
        await self.repo.session.refresh(tx)
        return TransactionEntry(
            id=tx.id,
            type=tx.type,
            amount=float(tx.amount),
            description=tx.description,
            matchday_number=None,
            created_at=tx.created_at,
        )

    async def delete_transaction(self, season_id: int, tx_id: int) -> bool:
        deleted = await self.repo.delete_transaction(tx_id)
        if not deleted:
            raise NotFoundError("Transaction", tx_id)
        await self.repo.session.commit()
        return True

    async def _get_weekly_rules(self, season_id: int) -> dict[int, Decimal]:
        """Load weekly_position rules from season_payments table."""
        payments = await self.season_repo.get_payments(season_id)
        return {
            p.position_rank: p.amount
            for p in payments
            if p.payment_type == "weekly_position" and p.position_rank is not None
        }

    # --- Weekly payment generation ---

    async def generate_weekly_payments(
        self,
        season_id: int,
        matchday_id: int,
    ) -> int:
        """Generate weekly_payment transactions for a matchday.

        Idempotent: skips if payments already exist for this matchday.
        Returns the number of transactions created.
        """
        existing = await self.repo.count_weekly_payments(matchday_id)
        if existing > 0:
            logger.debug(
                "generate_weekly_payments: matchday_id=%d already has %d payments, skip",
                matchday_id,
                existing,
            )
            return 0

        rankings = await self.repo.get_matchday_rankings(matchday_id)
        if not rankings:
            return 0

        rules = await self._get_weekly_rules(season_id)
        if not rules:
            logger.warning(
                "generate_weekly_payments: no weekly_position rules for season %d",
                season_id,
            )
            return 0

        pairs = compute_weekly_amounts(rankings, rules)
        created = 0
        for participant_id, amount in pairs:
            if amount > 0:
                await self.repo.create_transaction(
                    season_id=season_id,
                    participant_id=participant_id,
                    tx_type="weekly_payment",
                    amount=amount,
                    description=None,
                    matchday_id=matchday_id,
                )
                created += 1

        logger.info(
            "generate_weekly_payments: matchday_id=%d — created %d transactions",
            matchday_id,
            created,
        )
        return created
