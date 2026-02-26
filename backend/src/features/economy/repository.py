from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.transaction import Transaction
from src.shared.models.user import User


@dataclass
class ParticipantBalanceRow:
    participant_id: int
    display_name: str
    initial_fee: Decimal
    weekly_total: Decimal
    draft_fees: Decimal
    net_balance: Decimal


@dataclass
class TransactionRow:
    id: int
    type: str
    amount: Decimal
    description: str | None
    matchday_number: int | None
    created_at: datetime


class EconomyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_balances(self, season_id: int) -> list[ParticipantBalanceRow]:
        initial_fee = func.coalesce(
            func.sum(
                case(
                    (Transaction.type == "initial_fee", Transaction.amount),
                    else_=0,
                ),
            ),
            0,
        )
        weekly_total = func.coalesce(
            func.sum(
                case(
                    (Transaction.type == "weekly_payment", Transaction.amount),
                    else_=0,
                ),
            ),
            0,
        )
        draft_fees = func.coalesce(
            func.sum(
                case(
                    (Transaction.type == "winter_draft_fee", Transaction.amount),
                    else_=0,
                ),
            ),
            0,
        )
        net_balance = func.coalesce(func.sum(Transaction.amount), 0)

        stmt = (
            select(
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                initial_fee.label("initial_fee"),
                weekly_total.label("weekly_total"),
                draft_fees.label("draft_fees"),
                net_balance.label("net_balance"),
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .outerjoin(
                Transaction,
                (Transaction.participant_id == SeasonParticipant.id)
                & (Transaction.season_id == season_id),
            )
            .where(SeasonParticipant.season_id == season_id)
            .group_by(SeasonParticipant.id, User.display_name)
            .order_by(net_balance.desc())
        )

        result = await self.session.execute(stmt)
        return [
            ParticipantBalanceRow(
                participant_id=row.participant_id,
                display_name=row.display_name,
                initial_fee=row.initial_fee,
                weekly_total=row.weekly_total,
                draft_fees=row.draft_fees,
                net_balance=row.net_balance,
            )
            for row in result.all()
        ]

    async def get_transactions(
        self, season_id: int, participant_id: int,
    ) -> list[TransactionRow]:
        stmt = (
            select(
                Transaction.id,
                Transaction.type,
                Transaction.amount,
                Transaction.description,
                Matchday.number.label("matchday_number"),
                Transaction.created_at,
            )
            .outerjoin(Matchday, Transaction.matchday_id == Matchday.id)
            .where(
                Transaction.season_id == season_id,
                Transaction.participant_id == participant_id,
            )
            .order_by(Transaction.created_at.asc())
        )

        result = await self.session.execute(stmt)
        return [
            TransactionRow(
                id=row.id,
                type=row.type,
                amount=row.amount,
                description=row.description,
                matchday_number=row.matchday_number,
                created_at=row.created_at,
            )
            for row in result.all()
        ]

    async def get_participant_display_name(
        self, participant_id: int,
    ) -> str | None:
        stmt = (
            select(User.display_name)
            .join(SeasonParticipant, SeasonParticipant.user_id == User.id)
            .where(SeasonParticipant.id == participant_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_participant_net_balance(
        self, season_id: int, participant_id: int,
    ) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.season_id == season_id,
                Transaction.participant_id == participant_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create_transaction(
        self,
        season_id: int,
        participant_id: int,
        tx_type: str,
        amount: Decimal,
        description: str | None = None,
        matchday_id: int | None = None,
    ) -> Transaction:
        tx = Transaction(
            season_id=season_id,
            participant_id=participant_id,
            type=tx_type,
            amount=amount,
            description=description,
            matchday_id=matchday_id,
        )
        self.session.add(tx)
        return tx

    async def delete_transaction(self, tx_id: int) -> bool:
        tx = await self.session.get(Transaction, tx_id)
        if tx is None:
            return False
        await self.session.delete(tx)
        return True
