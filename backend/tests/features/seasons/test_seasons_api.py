from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.season import ScoringRule, Season, SeasonPayment, ValidFormation


@pytest.fixture
async def seed_seasons(db_session: AsyncSession) -> list[Season]:
    s1 = Season(
        name="2023-2024", status="finished", matchday_start=1, matchday_end=38,
        matchday_current=38, matchday_scanned=38, draft_pool_size=26,
        lineup_deadline_min=30, total_participants=8,
    )
    s2 = Season(
        name="2024-2025", status="active", matchday_start=1,
        matchday_current=20, matchday_scanned=20, draft_pool_size=26,
        lineup_deadline_min=30, total_participants=8,
    )
    db_session.add_all([s1, s2])
    await db_session.flush()
    return [s1, s2]


@pytest.fixture
async def seed_scoring_rules(
    db_session: AsyncSession, seed_seasons: list[Season],
) -> list[ScoringRule]:
    season = seed_seasons[1]
    rules = [
        ScoringRule(
            season_id=season.id, rule_key="goal", position="DEL",
            value=Decimal("5.00"), description="Gol delantero",
        ),
        ScoringRule(
            season_id=season.id, rule_key="goal", position="MED",
            value=Decimal("7.00"), description="Gol mediocampista",
        ),
        ScoringRule(
            season_id=season.id, rule_key="assist", position=None,
            value=Decimal("2.00"), description="Asistencia",
        ),
    ]
    db_session.add_all(rules)
    await db_session.flush()
    return rules


@pytest.fixture
async def seed_payments(
    db_session: AsyncSession, seed_seasons: list[Season],
) -> list[SeasonPayment]:
    season = seed_seasons[1]
    payments = [
        SeasonPayment(
            season_id=season.id, payment_type="initial_fee",
            amount=Decimal("50.00"), description="Cuota inicial",
        ),
        SeasonPayment(
            season_id=season.id, payment_type="weekly_position", position_rank=8,
            amount=Decimal("5.00"), description="Último de la jornada",
        ),
    ]
    db_session.add_all(payments)
    await db_session.flush()
    return payments


@pytest.fixture
async def seed_formations(db_session: AsyncSession) -> list[ValidFormation]:
    formations = [
        ValidFormation(formation="1-3-4-3", defenders=3, midfielders=4, forwards=3),
        ValidFormation(formation="1-4-4-2", defenders=4, midfielders=4, forwards=2),
    ]
    db_session.add_all(formations)
    await db_session.flush()
    return formations


class TestListSeasons:
    async def test_returns_empty_list(self, client: AsyncClient) -> None:
        resp = await client.get("/api/seasons")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_seasons_ordered_desc(
        self, client: AsyncClient, seed_seasons: list[Season],
    ) -> None:
        resp = await client.get("/api/seasons")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "2024-2025"
        assert data[1]["name"] == "2023-2024"

    async def test_season_summary_fields(
        self, client: AsyncClient, seed_seasons: list[Season],
    ) -> None:
        resp = await client.get("/api/seasons")
        season = resp.json()[0]
        assert set(season.keys()) == {"id", "name", "status", "total_participants"}


class TestGetCurrentSeason:
    async def test_returns_active_season(
        self, client: AsyncClient, seed_seasons: list[Season],
    ) -> None:
        resp = await client.get("/api/seasons/current")
        assert resp.status_code == 200
        assert resp.json()["name"] == "2024-2025"
        assert resp.json()["status"] == "active"

    async def test_returns_404_when_no_seasons(self, client: AsyncClient) -> None:
        resp = await client.get("/api/seasons/current")
        assert resp.status_code == 404


class TestGetSeason:
    async def test_returns_season_detail(
        self, client: AsyncClient, seed_seasons: list[Season],
    ) -> None:
        season_id = seed_seasons[0].id
        resp = await client.get(f"/api/seasons/{season_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "2023-2024"
        assert data["matchday_start"] == 1
        assert data["matchday_end"] == 38

    async def test_returns_404_for_missing(self, client: AsyncClient) -> None:
        resp = await client.get("/api/seasons/9999")
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"


class TestGetScoringRules:
    async def test_returns_rules_for_season(
        self, client: AsyncClient, seed_seasons: list[Season],
        seed_scoring_rules: list[ScoringRule],
    ) -> None:
        season_id = seed_seasons[1].id
        resp = await client.get(f"/api/seasons/{season_id}/scoring-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["rule_key"] == "assist"

    async def test_returns_404_for_missing_season(self, client: AsyncClient) -> None:
        resp = await client.get("/api/seasons/9999/scoring-rules")
        assert resp.status_code == 404


class TestGetPayments:
    async def test_returns_payments_for_season(
        self, client: AsyncClient, seed_seasons: list[Season],
        seed_payments: list[SeasonPayment],
    ) -> None:
        season_id = seed_seasons[1].id
        resp = await client.get(f"/api/seasons/{season_id}/payments")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_returns_404_for_missing_season(self, client: AsyncClient) -> None:
        resp = await client.get("/api/seasons/9999/payments")
        assert resp.status_code == 404


class TestGetFormations:
    async def test_returns_formations(
        self, client: AsyncClient, seed_formations: list[ValidFormation],
    ) -> None:
        resp = await client.get("/api/seasons/formations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["formation"] == "1-3-4-3"
