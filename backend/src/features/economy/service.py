from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
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
    Which is why a matchday whose points are not in yet must never be paid:
    everyone still at zero ties with the last one and pays his amount, the
    highest of the table (J6 of 2026-27 charged 2 € to whoever finished first).
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

    return [(rankings[i].participant_id, amounts[i]) for i in range(n)]


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
        Tournament seasons (Mundial, Eurocopa, Copa América) don't use
        weekly position payments — the function short-circuits.

        Returns the number of transactions created.
        """
        season = await self.season_repo.get_by_id(season_id)
        if season is not None and not season.weekly_payments_enabled:
            logger.debug(
                "generate_weekly_payments: season_id=%d has weekly payments disabled, skip",
                season_id,
            )
            return 0

        existing = await self.repo.count_weekly_payments(matchday_id)
        if existing > 0:
            logger.debug(
                "generate_weekly_payments: matchday_id=%d already has %d payments, skip",
                matchday_id,
                existing,
            )
            return 0

        due = await self._weekly_due(season_id, matchday_id)
        if due is None:
            return 0
        await self._write_weekly(season_id, matchday_id, due)
        logger.info(
            "generate_weekly_payments: matchday_id=%d — created %d transactions",
            matchday_id,
            len(due),
        )
        return len(due)

    async def _weekly_due(self, season_id: int, matchday_id: int) -> dict[int, Decimal] | None:
        """What this matchday should charge each participant, or None while it
        cannot be charged at all."""
        if not await self._can_be_paid(season_id, matchday_id):
            return None

        rankings = await self.repo.get_matchday_rankings(matchday_id)
        if not rankings:
            return None
        # Every participant on the same points is not a ranking: it is a
        # matchday that has not been scored, and paying it charges everyone the
        # last one's amount.
        if len({row.total_points for row in rankings}) == 1:
            logger.warning(
                "weekly payments: matchday_id=%d has every participant on %d points, "
                "nothing to rank, skip",
                matchday_id,
                rankings[0].total_points,
            )
            return None

        rules = await self._get_weekly_rules(season_id)
        if not rules:
            logger.warning(
                "weekly payments: no weekly_position rules for season %d",
                season_id,
            )
            return None

        # Only who pays gets a row.
        return {
            participant_id: amount
            for participant_id, amount in compute_weekly_amounts(rankings, rules)
            if amount > 0
        }

    async def _write_weekly(
        self, season_id: int, matchday_id: int, due: dict[int, Decimal]
    ) -> None:
        for participant_id, amount in due.items():
            await self.repo.create_transaction(
                season_id=season_id,
                participant_id=participant_id,
                tx_type="weekly_payment",
                amount=amount,
                description=None,
                matchday_id=matchday_id,
            )

    async def _can_be_paid(self, season_id: int, matchday_id: int) -> bool:
        season = await self.season_repo.get_by_id(season_id)
        if season is not None and not season.weekly_payments_enabled:
            return False
        return await self._points_are_final(matchday_id)

    async def weekly_payments_need_redoing(self, season_id: int, matchday_id: int) -> bool:
        """Whether what this matchday charges differs from what its ranking
        says it should. Answers without writing, for the close preview — which
        asks before the close has written the scores, and is told yes then,
        since that close is going to pay."""
        if not await self._can_be_paid(season_id, matchday_id):
            return False
        if not await self.repo.get_matchday_rankings(matchday_id):
            return True
        due = await self._weekly_due(season_id, matchday_id)
        return due is not None and due != await self.repo.weekly_payments(matchday_id)

    async def sync_weekly_payments(self, season_id: int, matchday_id: int) -> tuple[int, int]:
        """Make the matchday charge what its ranking says: (removed, written).

        Closing a matchday goes through here, so payments written while its
        points were still coming in are put right the moment it is closed for
        real. Payments that already match are left untouched, so closing again
        moves no money.
        """
        due = await self._weekly_due(season_id, matchday_id)
        if due is None or due == await self.repo.weekly_payments(matchday_id):
            return 0, 0
        deleted = await self.repo.delete_weekly_payments(matchday_id)
        await self._write_weekly(season_id, matchday_id, due)
        logger.info(
            "sync_weekly_payments: matchday_id=%d — removed %d, wrote %d",
            matchday_id,
            deleted,
            len(due),
        )
        return deleted, len(due)

    async def regenerate_weekly_payments(
        self,
        season_id: int,
        matchday_id: int,
    ) -> int:
        """Delete existing weekly_payment transactions and regenerate from current rankings.

        With the points still coming in, what is there is left alone: deleting
        it and writing nothing would look like a paid-up matchday.
        """
        if not await self._points_are_final(matchday_id):
            return 0
        deleted = await self.repo.delete_weekly_payments(matchday_id)
        if deleted:
            logger.info(
                "regenerate_weekly_payments: matchday_id=%d — deleted %d old payments",
                matchday_id,
                deleted,
            )
        return await self.generate_weekly_payments(season_id, matchday_id)

    async def _points_are_final(self, matchday_id: int) -> bool:
        """Whether the matchday can be paid: every counting match of it has its
        result and its player stats, so the ranking that decides who pays what
        is the real one. A postponed match that still counts holds the whole
        matchday back until it is played.

        The matchday's own ``stats_ok`` also answers yes, for the seasons
        brought over from the old site, whose matches carry no such flag. The
        status is not read: those seasons call it "completed" and the new ones
        "finished"."""
        matchday = await self.repo.get_matchday(matchday_id)
        if matchday is None:
            return False
        if matchday.stats_ok:
            return True
        counting, pending = await self.repo.counting_matches(matchday_id)
        if counting == 0 or pending:
            logger.info(
                "weekly payments: matchday_id=%d has %d counting match(es), %d still to play or "
                "scrape, not paying",
                matchday_id,
                counting,
                pending,
            )
            return False
        return True

    async def regenerate_all_weekly_payments(
        self,
        season_id: int,
    ) -> dict[str, int]:
        """Regenerate weekly payments for ALL counting matchdays in a season."""
        from src.shared.models.matchday import Matchday

        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        # Get all counting matchdays with stats_ok
        stmt = (
            select(Matchday.id, Matchday.number)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                Matchday.stats_ok.is_(True),
            )
            .order_by(Matchday.number)
        )
        result = await self.repo.session.execute(stmt)
        matchdays = result.all()

        total_deleted = 0
        total_created = 0
        for md_id, md_number in matchdays:
            deleted = await self.repo.delete_weekly_payments(md_id)
            total_deleted += deleted
            created = await self.generate_weekly_payments(season_id, md_id)
            total_created += created
            logger.info(
                "regenerate_all: J%d — deleted %d, created %d",
                md_number,
                deleted,
                created,
            )

        await self.repo.session.commit()
        return {
            "matchdays_processed": len(matchdays),
            "deleted": total_deleted,
            "created": total_created,
        }
