"""Survivors ranking: alive vs eliminated players per participant (tournaments)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from src.features.burger_ranking.survivors import SurvivorsService
from src.features.tournaments.service import TournamentService
from src.shared.models import (
    Match,
    Matchday,
    Player,
    Season,
    SeasonParticipant,
    Team,
    User,
)

# Two groups of 4. Knockout: a single tie M1 = 1A vs 2B.
CONFIG = {
    "groups": {"matchdays": [1]},
    "knockout": {
        "rounds": [
            {
                "name": "Semis",
                "matchday": 2,
                "pairings": [{"code": "M1", "home": "1A", "away": "2B"}],
            }
        ]
    },
}


async def _seed(db_session):
    season = Season(
        name="Cup 26",
        matchday_start=1,
        kind="tournament",
        tournament_type="mundial",
        tournament_config=CONFIG,
    )
    db_session.add(season)
    await db_session.flush()

    teams: dict[str, Team] = {}
    layout = {"A": ["A1", "A2", "A3", "A4"], "B": ["B1", "B2", "B3", "B4"]}
    for grp, names in layout.items():
        for n in names:
            t = Team(season_id=season.id, name=n, slug=n.lower(), tournament_group=grp)
            db_session.add(t)
            teams[n] = t
    mds = {n: Matchday(season_id=season.id, number=n) for n in (1, 2)}
    db_session.add_all(mds.values())
    await db_session.flush()

    # Group stage (J1) — decide a clear order in each group.
    # A: A1 > A2 > A3 > A4 ; B: B1 > B2 > B3 > B4.
    def gm(h, a, hs, as_):
        return Match(
            matchday_id=mds[1].id,
            home_team_id=teams[h].id,
            away_team_id=teams[a].id,
            home_score=hs,
            away_score=as_,
        )

    db_session.add_all(
        [
            gm("A1", "A4", 3, 0),
            gm("A2", "A3", 1, 0),
            gm("B1", "B4", 3, 0),
            gm("B2", "B3", 1, 0),
        ]
    )
    await db_session.flush()
    return season, teams, mds


@pytest.mark.asyncio
async def test_team_status_group_stage_not_done(db_session) -> None:
    """No best-thirds resolvable (single tie config) -> everyone alive."""
    season, teams, _ = await _seed(db_session)
    status = await TournamentService(db_session).get_team_status(season.id)
    # This config has no 12-group third table, so group_stage_done is False
    # and nobody is eliminated yet (alive until they fall).
    assert status.group_stage_done is False
    assert status.eliminated_team_ids == []
    assert len(status.alive_team_ids) == 8


@pytest.mark.asyncio
async def test_survivors_counts_knockout_loser_as_eliminated(db_session) -> None:
    season, teams, mds = await _seed(db_session)

    # Play the KO tie M1 = 1A(A1) vs 2B(B2): A1 wins, B2 eliminated.
    db_session.add(
        Match(
            matchday_id=mds[2].id,
            home_team_id=teams["A1"].id,
            away_team_id=teams["B2"].id,
            home_score=2,
            away_score=0,
            played_at=datetime(2026, 7, 1, 20, tzinfo=UTC),
        )
    )

    # One participant owning A1 (alive) and B2 (eliminated).
    user = User(username="mgr", display_name="Mgr", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    part = SeasonParticipant(season_id=season.id, user_id=user.id, is_active=True)
    db_session.add(part)
    await db_session.flush()
    for name, pos in [("A1", "DEL"), ("B2", "DEF")]:
        db_session.add(
            Player(
                season_id=season.id,
                team_id=teams[name].id,
                name=name,
                display_name=name,
                slug=name.lower(),
                position=pos,
                owner_id=part.id,
            )
        )
    await db_session.flush()

    resp = await SurvivorsService(db_session).get_ranking(season.id)
    assert resp is not None
    assert len(resp.entries) == 1
    entry = resp.entries[0]
    assert entry.total == 2
    assert entry.eliminated_count == 1
    assert entry.alive_count == 1
    eliminated = {p.player_name for p in entry.players if not p.alive}
    assert eliminated == {"B2"}


@pytest.mark.asyncio
async def test_survivors_returns_none_for_league(db_session) -> None:
    season = Season(name="Liga 25-26", matchday_start=1, kind="league")
    db_session.add(season)
    await db_session.flush()
    assert await SurvivorsService(db_session).get_ranking(season.id) is None
