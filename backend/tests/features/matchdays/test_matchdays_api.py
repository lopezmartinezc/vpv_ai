from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.season import Season
from src.shared.models.team import Team
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
async def teams(db_session: AsyncSession, season: Season) -> list[Team]:
    t1 = Team(season_id=season.id, name="Real Madrid", slug="real-madrid")
    t2 = Team(season_id=season.id, name="Barcelona", slug="barcelona")
    db_session.add_all([t1, t2])
    await db_session.flush()
    return [t1, t2]


@pytest.fixture
async def matchday_with_data(
    db_session: AsyncSession,
    season: Season,
    teams: list[Team],
    participants: list[SeasonParticipant],
) -> Matchday:
    md = Matchday(
        season_id=season.id, number=5, status="completed",
        counts=True, stats_ok=True,
    )
    db_session.add(md)
    await db_session.flush()

    m1 = Match(
        matchday_id=md.id, home_team_id=teams[0].id,
        away_team_id=teams[1].id, home_score=2, away_score=1, counts=True,
    )
    db_session.add(m1)
    await db_session.flush()

    scores = [
        ParticipantMatchdayScore(
            participant_id=participants[0].id,
            matchday_id=md.id, total_points=95, ranking=1,
        ),
        ParticipantMatchdayScore(
            participant_id=participants[1].id,
            matchday_id=md.id, total_points=80, ranking=2,
        ),
    ]
    db_session.add_all(scores)
    await db_session.flush()
    return md


@pytest.fixture
async def matchday_no_stats(
    db_session: AsyncSession, season: Season,
) -> Matchday:
    md = Matchday(
        season_id=season.id, number=10, status="pending",
        counts=True, stats_ok=False,
    )
    db_session.add(md)
    await db_session.flush()
    return md


@pytest.fixture
async def lineup_with_players(
    db_session: AsyncSession,
    season: Season,
    matchday_with_data: Matchday,
    participants: list[SeasonParticipant],
    teams: list[Team],
) -> Lineup:
    player = Player(
        season_id=season.id, team_id=teams[0].id,
        name="Jude Bellingham", display_name="Bellingham",
        slug="bellingham", position="MED",
    )
    db_session.add(player)
    await db_session.flush()

    lineup = Lineup(
        participant_id=participants[0].id,
        matchday_id=matchday_with_data.id,
        formation="1-4-3-3", confirmed=True, total_points=95,
    )
    db_session.add(lineup)
    await db_session.flush()

    lp = LineupPlayer(
        lineup_id=lineup.id, player_id=player.id,
        position_slot="MED", display_order=5, points=12,
    )
    db_session.add(lp)
    await db_session.flush()

    stat = PlayerStat(
        player_id=player.id, matchday_id=matchday_with_data.id,
        position="MED", played=True, processed=True,
        pts_play=1, pts_starter=1, pts_result=2,
        pts_clean_sheet=0, pts_goals=0, pts_penalty_goals=0,
        pts_assists=5, pts_penalties_saved=0, pts_woodwork=0,
        pts_penalties_won=0, pts_penalties_missed=0,
        pts_own_goals=0, pts_yellow=0, pts_red=0,
        pts_pen_committed=0, pts_marca=2, pts_as=1,
        pts_marca_as=3, pts_total=12,
    )
    db_session.add(stat)
    await db_session.flush()
    return lineup


class TestListMatchdays:
    async def test_returns_matchdays_for_season(
        self, client: AsyncClient, season: Season,
        matchday_with_data: Matchday,
    ) -> None:
        resp = await client.get(f"/api/matchdays/{season.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["season_id"] == season.id
        assert len(data["matchdays"]) == 1
        assert data["matchdays"][0]["number"] == 5
        assert data["matchdays"][0]["stats_ok"] is True

    async def test_excludes_future_matchdays_by_default(
        self, client: AsyncClient, season: Season,
        matchday_with_data: Matchday, matchday_no_stats: Matchday,
    ) -> None:
        resp = await client.get(f"/api/matchdays/{season.id}")
        data = resp.json()
        assert len(data["matchdays"]) == 1

    async def test_includes_all_when_stats_ok_only_false(
        self, client: AsyncClient, season: Season,
        matchday_with_data: Matchday, matchday_no_stats: Matchday,
    ) -> None:
        resp = await client.get(
            f"/api/matchdays/{season.id}?stats_ok_only=false"
        )
        data = resp.json()
        assert len(data["matchdays"]) == 2

    async def test_returns_404_for_missing_season(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/matchdays/9999")
        assert resp.status_code == 404


class TestMatchdayDetail:
    async def test_returns_matches_and_scores(
        self, client: AsyncClient, season: Season,
        matchday_with_data: Matchday,
    ) -> None:
        resp = await client.get(f"/api/matchdays/{season.id}/5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["number"] == 5
        assert len(data["matches"]) == 1
        assert data["matches"][0]["home_team"] == "Real Madrid"
        assert data["matches"][0]["home_score"] == 2
        assert len(data["scores"]) == 2
        assert data["scores"][0]["total_points"] == 95
        assert data["scores"][0]["rank"] == 1

    async def test_scores_ordered_by_ranking(
        self, client: AsyncClient, season: Season,
        matchday_with_data: Matchday,
    ) -> None:
        resp = await client.get(f"/api/matchdays/{season.id}/5")
        scores = resp.json()["scores"]
        assert scores[0]["rank"] == 1
        assert scores[1]["rank"] == 2
        assert scores[0]["total_points"] > scores[1]["total_points"]

    async def test_returns_404_for_missing_season(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/matchdays/9999/5")
        assert resp.status_code == 404

    async def test_returns_404_for_missing_matchday(
        self, client: AsyncClient, season: Season,
    ) -> None:
        resp = await client.get(f"/api/matchdays/{season.id}/99")
        assert resp.status_code == 404


class TestLineupDetail:
    async def test_returns_lineup_with_players(
        self, client: AsyncClient, season: Season,
        matchday_with_data: Matchday,
        participants: list[SeasonParticipant],
        lineup_with_players: Lineup,
    ) -> None:
        resp = await client.get(
            f"/api/matchdays/{season.id}/5/lineup/{participants[0].id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["formation"] == "1-4-3-3"
        assert data["total_points"] == 95
        assert len(data["players"]) == 1
        player = data["players"][0]
        assert player["player_name"] == "Bellingham"
        assert player["position_slot"] == "MED"
        assert player["points"] == 12

    async def test_returns_score_breakdown(
        self, client: AsyncClient, season: Season,
        matchday_with_data: Matchday,
        participants: list[SeasonParticipant],
        lineup_with_players: Lineup,
    ) -> None:
        resp = await client.get(
            f"/api/matchdays/{season.id}/5/lineup/{participants[0].id}"
        )
        player = resp.json()["players"][0]
        breakdown = player["score_breakdown"]
        assert breakdown is not None
        assert breakdown["pts_total"] == 12
        assert breakdown["pts_assists"] == 5
        assert breakdown["pts_marca"] == 2

    async def test_returns_404_for_missing_lineup(
        self, client: AsyncClient, season: Season,
        matchday_with_data: Matchday,
        participants: list[SeasonParticipant],
    ) -> None:
        resp = await client.get(
            f"/api/matchdays/{season.id}/5/lineup/{participants[1].id}"
        )
        assert resp.status_code == 404

    async def test_returns_404_for_missing_matchday(
        self, client: AsyncClient, season: Season,
        participants: list[SeasonParticipant],
    ) -> None:
        resp = await client.get(
            f"/api/matchdays/{season.id}/99/lineup/{participants[0].id}"
        )
        assert resp.status_code == 404
