from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.matchday import Matchday
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
async def players_with_stats(
    db_session: AsyncSession,
    season: Season,
    teams: list[Team],
    participants: list[SeasonParticipant],
) -> list[Player]:
    # Alice owns 3 players, Bob owns 1
    p1 = Player(
        season_id=season.id, team_id=teams[0].id, owner_id=participants[0].id,
        name="Bellingham", display_name="Bellingham", slug="bellingham",
        position="MED",
    )
    p2 = Player(
        season_id=season.id, team_id=teams[0].id, owner_id=participants[0].id,
        name="Vinicius", display_name="Vinicius", slug="vinicius",
        position="DEL",
    )
    p3 = Player(
        season_id=season.id, team_id=teams[1].id, owner_id=participants[0].id,
        name="Ter Stegen", display_name="Ter Stegen", slug="ter-stegen",
        position="POR",
    )
    p4 = Player(
        season_id=season.id, team_id=teams[1].id, owner_id=participants[1].id,
        name="Lamine Yamal", display_name="Lamine Yamal", slug="lamine-yamal",
        position="DEL",
    )
    # Free agent (no owner)
    p5 = Player(
        season_id=season.id, team_id=teams[0].id, owner_id=None,
        name="Modric", display_name="Modric", slug="modric",
        position="MED",
    )
    db_session.add_all([p1, p2, p3, p4, p5])
    await db_session.flush()

    # Create matchdays and stats for season points
    md1 = Matchday(
        season_id=season.id, number=1, status="completed",
        counts=True, stats_ok=True,
    )
    md2 = Matchday(
        season_id=season.id, number=2, status="completed",
        counts=True, stats_ok=True,
    )
    md_no_count = Matchday(
        season_id=season.id, number=3, status="completed",
        counts=False, stats_ok=True,
    )
    db_session.add_all([md1, md2, md_no_count])
    await db_session.flush()

    stats = [
        # Bellingham: 15+20 = 35 (counting), +100 (non-counting)
        PlayerStat(
            player_id=p1.id, matchday_id=md1.id, position="MED",
            played=True, processed=True, pts_total=15,
        ),
        PlayerStat(
            player_id=p1.id, matchday_id=md2.id, position="MED",
            played=True, processed=True, pts_total=20,
        ),
        PlayerStat(
            player_id=p1.id, matchday_id=md_no_count.id, position="MED",
            played=True, processed=True, pts_total=100,
        ),
        # Vinicius: 25 (counting only)
        PlayerStat(
            player_id=p2.id, matchday_id=md1.id, position="DEL",
            played=True, processed=True, pts_total=25,
        ),
        # Ter Stegen: 10 (counting only)
        PlayerStat(
            player_id=p3.id, matchday_id=md1.id, position="POR",
            played=True, processed=True, pts_total=10,
        ),
        # Lamine Yamal: 30 (counting only)
        PlayerStat(
            player_id=p4.id, matchday_id=md1.id, position="DEL",
            played=True, processed=True, pts_total=30,
        ),
    ]
    db_session.add_all(stats)
    await db_session.flush()

    # Participant matchday scores for season totals
    scores = [
        ParticipantMatchdayScore(
            participant_id=participants[0].id, matchday_id=md1.id,
            total_points=50, ranking=1,
        ),
        ParticipantMatchdayScore(
            participant_id=participants[0].id, matchday_id=md2.id,
            total_points=20, ranking=2,
        ),
        ParticipantMatchdayScore(
            participant_id=participants[1].id, matchday_id=md1.id,
            total_points=30, ranking=2,
        ),
    ]
    db_session.add_all(scores)
    await db_session.flush()

    return [p1, p2, p3, p4, p5]


class TestListSquads:
    async def test_returns_squads_for_season(
        self, client: AsyncClient, season: Season,
        players_with_stats: list[Player],
    ) -> None:
        resp = await client.get(f"/api/squads/{season.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["season_id"] == season.id
        assert len(data["squads"]) == 2

    async def test_squad_summary_has_correct_counts(
        self, client: AsyncClient, season: Season,
        players_with_stats: list[Player],
    ) -> None:
        resp = await client.get(f"/api/squads/{season.id}")
        squads = resp.json()["squads"]
        # Alice has 3 players: 1 POR, 1 MED, 1 DEL
        alice = next(s for s in squads if s["display_name"] == "Alice")
        assert alice["total_players"] == 3
        assert alice["positions"]["POR"] == 1
        assert alice["positions"]["MED"] == 1
        assert alice["positions"]["DEL"] == 1
        assert alice["positions"]["DEF"] == 0

    async def test_squad_summary_includes_season_points(
        self, client: AsyncClient, season: Season,
        players_with_stats: list[Player],
    ) -> None:
        resp = await client.get(f"/api/squads/{season.id}")
        squads = resp.json()["squads"]
        alice = next(s for s in squads if s["display_name"] == "Alice")
        # Alice: 50 + 20 = 70 (from participant_matchday_scores, counts=true)
        assert alice["season_points"] == 70

    async def test_returns_404_for_missing_season(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/squads/9999")
        assert resp.status_code == 404


class TestSquadDetail:
    async def test_returns_players_for_participant(
        self, client: AsyncClient, season: Season,
        participants: list[SeasonParticipant],
        players_with_stats: list[Player],
    ) -> None:
        resp = await client.get(
            f"/api/squads/{season.id}/{participants[0].id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "Alice"
        assert len(data["players"]) == 3

    async def test_player_season_points_excludes_non_counting(
        self, client: AsyncClient, season: Season,
        participants: list[SeasonParticipant],
        players_with_stats: list[Player],
    ) -> None:
        resp = await client.get(
            f"/api/squads/{season.id}/{participants[0].id}"
        )
        players = resp.json()["players"]
        bellingham = next(p for p in players if p["display_name"] == "Bellingham")
        # 15+20 = 35 (md3 with counts=false excluded)
        assert bellingham["season_points"] == 35

    async def test_players_ordered_by_position_then_points(
        self, client: AsyncClient, season: Season,
        participants: list[SeasonParticipant],
        players_with_stats: list[Player],
    ) -> None:
        resp = await client.get(
            f"/api/squads/{season.id}/{participants[0].id}"
        )
        players = resp.json()["players"]
        positions = [p["position"] for p in players]
        # POR first, then DEL, then MED (sorted by position order, then points DESC)
        assert positions == ["POR", "MED", "DEL"]

    async def test_returns_404_for_missing_participant(
        self, client: AsyncClient, season: Season,
    ) -> None:
        resp = await client.get(f"/api/squads/{season.id}/9999")
        assert resp.status_code == 404
