from __future__ import annotations

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.draft import Draft, DraftPick
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.user import User


@pytest.fixture
async def season(db_session: AsyncSession) -> Season:
    s = Season(
        name="2024-2025", status="active", matchday_start=1, matchday_end=38,
        matchday_current=10, matchday_scanned=10, draft_pool_size=3,
        lineup_deadline_min=30, total_participants=3,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def users(db_session: AsyncSession) -> list[User]:
    u1 = User(username="alice", password_hash="x", display_name="Alice")
    u2 = User(username="bob", password_hash="x", display_name="Bob")
    u3 = User(username="carol", password_hash="x", display_name="Carol")
    db_session.add_all([u1, u2, u3])
    await db_session.flush()
    return [u1, u2, u3]


@pytest.fixture
async def participants(
    db_session: AsyncSession, season: Season, users: list[User],
) -> list[SeasonParticipant]:
    parts = [
        SeasonParticipant(
            season_id=season.id, user_id=users[i].id, draft_order=i + 1,
        )
        for i in range(3)
    ]
    db_session.add_all(parts)
    await db_session.flush()
    return parts


@pytest.fixture
async def teams(db_session: AsyncSession, season: Season) -> list[Team]:
    t1 = Team(season_id=season.id, name="Real Madrid", slug="real-madrid")
    t2 = Team(season_id=season.id, name="Barcelona", slug="barcelona")
    db_session.add_all([t1, t2])
    await db_session.flush()
    return [t1, t2]


@pytest.fixture
async def draft_with_picks(
    db_session: AsyncSession,
    season: Season,
    participants: list[SeasonParticipant],
    teams: list[Team],
) -> Draft:
    # Create players
    players = [
        Player(
            season_id=season.id, team_id=teams[0].id,
            owner_id=participants[0].id,
            name="Player A", display_name="Player A", slug="player-a",
            position="DEL",
        ),
        Player(
            season_id=season.id, team_id=teams[1].id,
            owner_id=participants[1].id,
            name="Player B", display_name="Player B", slug="player-b",
            position="MED",
        ),
        Player(
            season_id=season.id, team_id=teams[0].id,
            owner_id=participants[2].id,
            name="Player C", display_name="Player C", slug="player-c",
            position="POR",
        ),
        # Round 2 (snake reverses)
        Player(
            season_id=season.id, team_id=teams[1].id,
            owner_id=participants[2].id,
            name="Player D", display_name="Player D", slug="player-d",
            position="DEF",
        ),
        Player(
            season_id=season.id, team_id=teams[0].id,
            owner_id=participants[1].id,
            name="Player E", display_name="Player E", slug="player-e",
            position="DEF",
        ),
        Player(
            season_id=season.id, team_id=teams[1].id,
            owner_id=participants[0].id,
            name="Player F", display_name="Player F", slug="player-f",
            position="MED",
        ),
    ]
    db_session.add_all(players)
    await db_session.flush()

    # Create completed preseason draft
    draft = Draft(
        season_id=season.id, draft_type="snake", phase="preseason",
        status="completed", current_round=2, current_pick=6,
        started_at=datetime(2025, 7, 15, 18, 0),
        completed_at=datetime(2025, 7, 15, 19, 0),
    )
    db_session.add(draft)
    await db_session.flush()

    # 6 picks: round 1 forward (Alice, Bob, Carol), round 2 reverse (Carol, Bob, Alice)
    picks = [
        DraftPick(
            draft_id=draft.id, participant_id=participants[0].id,
            player_id=players[0].id, round_number=1, pick_number=1,
        ),
        DraftPick(
            draft_id=draft.id, participant_id=participants[1].id,
            player_id=players[1].id, round_number=1, pick_number=2,
        ),
        DraftPick(
            draft_id=draft.id, participant_id=participants[2].id,
            player_id=players[2].id, round_number=1, pick_number=3,
        ),
        DraftPick(
            draft_id=draft.id, participant_id=participants[2].id,
            player_id=players[3].id, round_number=2, pick_number=4,
        ),
        DraftPick(
            draft_id=draft.id, participant_id=participants[1].id,
            player_id=players[4].id, round_number=2, pick_number=5,
        ),
        DraftPick(
            draft_id=draft.id, participant_id=participants[0].id,
            player_id=players[5].id, round_number=2, pick_number=6,
        ),
    ]
    db_session.add_all(picks)
    await db_session.flush()
    return draft


class TestListDrafts:
    async def test_returns_drafts_for_season(
        self, client: AsyncClient, season: Season,
        draft_with_picks: Draft,
    ) -> None:
        resp = await client.get(f"/api/drafts/{season.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["season_id"] == season.id
        assert len(data["drafts"]) == 1

    async def test_draft_summary_has_total_picks(
        self, client: AsyncClient, season: Season,
        draft_with_picks: Draft,
    ) -> None:
        resp = await client.get(f"/api/drafts/{season.id}")
        draft = resp.json()["drafts"][0]
        assert draft["phase"] == "preseason"
        assert draft["draft_type"] == "snake"
        assert draft["total_picks"] == 6

    async def test_returns_404_for_missing_season(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/drafts/9999")
        assert resp.status_code == 404


class TestDraftDetail:
    async def test_returns_picks_in_order(
        self, client: AsyncClient, season: Season,
        draft_with_picks: Draft,
    ) -> None:
        resp = await client.get(f"/api/drafts/{season.id}/preseason")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "preseason"
        assert data["draft_type"] == "snake"
        assert len(data["picks"]) == 6

    async def test_pick_contains_player_info(
        self, client: AsyncClient, season: Season,
        draft_with_picks: Draft,
    ) -> None:
        resp = await client.get(f"/api/drafts/{season.id}/preseason")
        first_pick = resp.json()["picks"][0]
        assert first_pick["pick_number"] == 1
        assert first_pick["round_number"] == 1
        assert first_pick["player_name"] == "Player A"
        assert first_pick["position"] == "DEL"
        assert first_pick["team_name"] == "Real Madrid"

    async def test_includes_participant_list(
        self, client: AsyncClient, season: Season,
        draft_with_picks: Draft,
    ) -> None:
        resp = await client.get(f"/api/drafts/{season.id}/preseason")
        participants = resp.json()["participants"]
        assert len(participants) == 3
        names = [p["display_name"] for p in participants]
        assert "Alice" in names

    async def test_returns_404_for_missing_phase(
        self, client: AsyncClient, season: Season,
        draft_with_picks: Draft,
    ) -> None:
        resp = await client.get(f"/api/drafts/{season.id}/winter")
        assert resp.status_code == 404

    async def test_returns_404_for_missing_season(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/drafts/9999/preseason")
        assert resp.status_code == 404
