from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.season import Season
from src.shared.models.transaction import Transaction
from src.shared.models.user import User


@pytest.fixture
async def season(db_session: AsyncSession) -> Season:
    s = Season(
        name="2024-2025", status="active", matchday_start=1, matchday_end=38,
        matchday_current=10, matchday_scanned=10, draft_pool_size=26,
        lineup_deadline_min=30, total_participants=2,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def users(db_session: AsyncSession) -> list[User]:
    u1 = User(username="alice", password_hash="x", display_name="Alice")
    u2 = User(username="bob", password_hash="x", display_name="Bob")
    db_session.add_all([u1, u2])
    await db_session.flush()
    return [u1, u2]


@pytest.fixture
async def participants(
    db_session: AsyncSession, season: Season, users: list[User],
) -> list[SeasonParticipant]:
    parts = [
        SeasonParticipant(season_id=season.id, user_id=u.id)
        for u in users
    ]
    db_session.add_all(parts)
    await db_session.flush()
    return parts


@pytest.fixture
async def transactions(
    db_session: AsyncSession,
    season: Season,
    participants: list[SeasonParticipant],
) -> list[Transaction]:
    md = Matchday(
        season_id=season.id, number=1, status="completed",
        counts=True, stats_ok=True,
    )
    db_session.add(md)
    await db_session.flush()

    txs = [
        # Alice: initial fee + weekly payment
        Transaction(
            season_id=season.id, participant_id=participants[0].id,
            matchday_id=None, type="initial_fee",
            amount=Decimal("50.00"), description="Cuota inicial",
        ),
        Transaction(
            season_id=season.id, participant_id=participants[0].id,
            matchday_id=md.id, type="weekly_payment",
            amount=Decimal("3.00"), description="Jornada 1 - puesto 7",
        ),
        # Bob: initial fee + winter draft fee
        Transaction(
            season_id=season.id, participant_id=participants[1].id,
            matchday_id=None, type="initial_fee",
            amount=Decimal("50.00"), description="Cuota inicial",
        ),
        Transaction(
            season_id=season.id, participant_id=participants[1].id,
            matchday_id=None, type="winter_draft_fee",
            amount=Decimal("2.00"), description="Draft invierno - 1 cambio",
        ),
    ]
    db_session.add_all(txs)
    await db_session.flush()
    return txs


class TestEconomyOverview:
    async def test_returns_balances_for_season(
        self, client: AsyncClient, season: Season,
        transactions: list[Transaction],
    ) -> None:
        resp = await client.get(f"/api/economy/{season.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["season_id"] == season.id
        assert len(data["balances"]) == 2

    async def test_balance_breakdown_is_correct(
        self, client: AsyncClient, season: Season,
        transactions: list[Transaction],
    ) -> None:
        resp = await client.get(f"/api/economy/{season.id}")
        balances = resp.json()["balances"]
        alice = next(b for b in balances if b["display_name"] == "Alice")
        assert float(alice["initial_fee"]) == 50.0
        assert float(alice["weekly_total"]) == 3.0
        assert float(alice["draft_fees"]) == 0.0
        assert float(alice["net_balance"]) == 53.0

    async def test_bob_has_draft_fees(
        self, client: AsyncClient, season: Season,
        transactions: list[Transaction],
    ) -> None:
        resp = await client.get(f"/api/economy/{season.id}")
        balances = resp.json()["balances"]
        bob = next(b for b in balances if b["display_name"] == "Bob")
        assert float(bob["initial_fee"]) == 50.0
        assert float(bob["draft_fees"]) == 2.0
        assert float(bob["net_balance"]) == 52.0

    async def test_returns_404_for_missing_season(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/economy/9999")
        assert resp.status_code == 404


class TestParticipantTransactions:
    async def test_returns_transactions_for_participant(
        self, client: AsyncClient, season: Season,
        participants: list[SeasonParticipant],
        transactions: list[Transaction],
    ) -> None:
        resp = await client.get(
            f"/api/economy/{season.id}/{participants[0].id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "Alice"
        assert len(data["transactions"]) == 2

    async def test_transaction_has_correct_fields(
        self, client: AsyncClient, season: Season,
        participants: list[SeasonParticipant],
        transactions: list[Transaction],
    ) -> None:
        resp = await client.get(
            f"/api/economy/{season.id}/{participants[0].id}"
        )
        txs = resp.json()["transactions"]
        weekly = next(t for t in txs if t["type"] == "weekly_payment")
        assert float(weekly["amount"]) == 3.0
        assert weekly["matchday_number"] == 1
        assert weekly["description"] == "Jornada 1 - puesto 7"

    async def test_net_balance_is_sum(
        self, client: AsyncClient, season: Season,
        participants: list[SeasonParticipant],
        transactions: list[Transaction],
    ) -> None:
        resp = await client.get(
            f"/api/economy/{season.id}/{participants[0].id}"
        )
        assert float(resp.json()["net_balance"]) == 53.0

    async def test_returns_404_for_missing_participant(
        self, client: AsyncClient, season: Season,
    ) -> None:
        resp = await client.get(f"/api/economy/{season.id}/9999")
        assert resp.status_code == 404
