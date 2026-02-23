from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.season import Season
from src.shared.models.user import User


@pytest.fixture
async def season(db_session: AsyncSession) -> Season:
    s = Season(
        name="2024-2025", status="active", matchday_start=1, matchday_end=38,
        matchday_current=10, matchday_scanned=10, draft_pool_size=26,
        lineup_deadline_min=30, total_participants=3,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def users(db_session: AsyncSession) -> list[User]:
    u1 = User(username="alice", password_hash="x", display_name="Alice")
    u2 = User(username="bob", password_hash="x", display_name="Bob")
    u3 = User(username="charlie", password_hash="x", display_name="Charlie")
    db_session.add_all([u1, u2, u3])
    await db_session.flush()
    return [u1, u2, u3]


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
async def matchdays_with_scores(
    db_session: AsyncSession,
    season: Season,
    participants: list[SeasonParticipant],
) -> None:
    md1 = Matchday(season_id=season.id, number=1, status="finished", counts=True)
    md2 = Matchday(season_id=season.id, number=2, status="finished", counts=True)
    md3 = Matchday(season_id=season.id, number=3, status="finished", counts=False)
    db_session.add_all([md1, md2, md3])
    await db_session.flush()

    alice, bob, charlie = participants
    scores = [
        # Matchday 1 (counts)
        ParticipantMatchdayScore(
            participant_id=alice.id, matchday_id=md1.id, total_points=80, ranking=1,
        ),
        ParticipantMatchdayScore(
            participant_id=bob.id, matchday_id=md1.id, total_points=70, ranking=2,
        ),
        ParticipantMatchdayScore(
            participant_id=charlie.id, matchday_id=md1.id, total_points=60, ranking=3,
        ),
        # Matchday 2 (counts)
        ParticipantMatchdayScore(
            participant_id=alice.id, matchday_id=md2.id, total_points=50, ranking=3,
        ),
        ParticipantMatchdayScore(
            participant_id=bob.id, matchday_id=md2.id, total_points=90, ranking=1,
        ),
        ParticipantMatchdayScore(
            participant_id=charlie.id, matchday_id=md2.id, total_points=70, ranking=2,
        ),
        # Matchday 3 (does NOT count)
        ParticipantMatchdayScore(
            participant_id=alice.id, matchday_id=md3.id, total_points=100, ranking=1,
        ),
        ParticipantMatchdayScore(
            participant_id=bob.id, matchday_id=md3.id, total_points=10, ranking=3,
        ),
    ]
    db_session.add_all(scores)
    await db_session.flush()


class TestStandings:
    async def test_returns_standings_sorted_by_points(
        self, client: AsyncClient, season: Season,
        matchdays_with_scores: None,
    ) -> None:
        resp = await client.get(f"/api/standings/{season.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["season_name"] == "2024-2025"
        entries = data["entries"]
        assert len(entries) == 3
        # Bob: 70+90=160, Alice: 80+50=130, Charlie: 60+70=130
        assert entries[0]["display_name"] == "Bob"
        assert entries[0]["total_points"] == 160
        assert entries[0]["rank"] == 1

    async def test_excludes_non_counting_matchdays(
        self, client: AsyncClient, season: Season,
        matchdays_with_scores: None,
    ) -> None:
        resp = await client.get(f"/api/standings/{season.id}")
        entries = resp.json()["entries"]
        # Alice has 100 pts in non-counting matchday 3, should NOT be included
        alice = next(e for e in entries if e["display_name"] == "Alice")
        assert alice["total_points"] == 130  # 80+50 only
        assert alice["matchdays_played"] == 2  # not 3

    async def test_calculates_avg_points(
        self, client: AsyncClient, season: Season,
        matchdays_with_scores: None,
    ) -> None:
        resp = await client.get(f"/api/standings/{season.id}")
        entries = resp.json()["entries"]
        bob = next(e for e in entries if e["display_name"] == "Bob")
        assert bob["avg_points"] == 80.0  # 160/2

    async def test_returns_404_for_missing_season(self, client: AsyncClient) -> None:
        resp = await client.get("/api/standings/9999")
        assert resp.status_code == 404

    async def test_empty_standings_when_no_scores(
        self, client: AsyncClient, season: Season,
        participants: list[SeasonParticipant],
    ) -> None:
        resp = await client.get(f"/api/standings/{season.id}")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 3
        assert all(e["total_points"] == 0 for e in entries)
        assert all(e["matchdays_played"] == 0 for e in entries)
