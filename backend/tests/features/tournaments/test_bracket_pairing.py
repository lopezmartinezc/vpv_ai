"""get_bracket must attach real matches to bracket slots by TEAMS, not order.

Regression for Mundial 2026 J4: once the round-of-32 fixtures existed as
real Match rows, get_bracket paired them to config slots by list index.
The DB returns matches in chronological (played_at) order while the config
pairings follow bracket order, so a match landed in the wrong slot (e.g.
M74's fixture wired into M75) and the whole knockout tree was scrambled —
and winners propagated into the wrong round-of-16 matches.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from src.features.tournaments.service import TournamentService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.season import Season
from src.shared.models.team import Team

CONFIG = {
    "groups": {"matchdays": [1]},
    "knockout": {
        "rounds": [
            {
                "name": "Semis",
                "matchday": 2,
                "pairings": [
                    {"code": "M1", "home": "1A", "away": "2B"},
                    {"code": "M2", "home": "1B", "away": "2A"},
                ],
            },
            {
                "name": "Final",
                "matchday": 3,
                "pairings": [{"code": "M3", "home": "W1", "away": "W2"}],
            },
        ]
    },
}


async def _seed(db_session) -> tuple[int, dict[str, Team]]:
    season = Season(
        name="Cup 26",
        matchday_start=1,
        kind="tournament",
        tournament_type="mundial",
        tournament_config=CONFIG,
    )
    db_session.add(season)
    await db_session.flush()

    t: dict[str, Team] = {}
    for name, grp in [("A1", "A"), ("A2", "A"), ("B1", "B"), ("B2", "B")]:
        team = Team(season_id=season.id, name=name, slug=name.lower(), tournament_group=grp)
        db_session.add(team)
        t[name] = team
    mds = {n: Matchday(season_id=season.id, number=n) for n in (1, 2, 3)}
    db_session.add_all(mds.values())
    await db_session.flush()

    # Group stage (J1): A1 > A2, B1 > B2  ->  1A=A1, 2A=A2, 1B=B1, 2B=B2.
    db_session.add_all(
        [
            Match(
                matchday_id=mds[1].id,
                home_team_id=t["A1"].id,
                away_team_id=t["A2"].id,
                home_score=2,
                away_score=0,
            ),
            Match(
                matchday_id=mds[1].id,
                home_team_id=t["B1"].id,
                away_team_id=t["B2"].id,
                home_score=2,
                away_score=0,
            ),
        ]
    )
    # Knockout (J2). Expected slots: M1 = 1A/2B = {A1,B2}; M2 = 1B/2A = {B1,A2}.
    # Insert them so chronological order is the REVERSE of bracket order: the
    # M2 fixture kicks off first. An index pairing would mislabel both.
    db_session.add_all(
        [
            Match(
                matchday_id=mds[2].id,
                home_team_id=t["B1"].id,
                away_team_id=t["A2"].id,
                home_score=1,
                away_score=0,
                played_at=datetime(2026, 7, 1, 18, tzinfo=UTC),
            ),
            Match(
                matchday_id=mds[2].id,
                home_team_id=t["A1"].id,
                away_team_id=t["B2"].id,
                home_score=3,
                away_score=1,
                played_at=datetime(2026, 7, 1, 22, tzinfo=UTC),
            ),
        ]
    )
    await db_session.flush()
    return season.id, t


@pytest.mark.asyncio
async def test_real_matches_attach_to_slot_by_teams(db_session) -> None:
    season_id, t = await _seed(db_session)

    bracket = await TournamentService(db_session).get_bracket(season_id)

    semis = next(r for r in bracket.rounds if r.name == "Semis")
    by_code = {m.match_code: m for m in semis.matches}

    # M1 must be the {A1,B2} fixture, M2 the {B1,A2} fixture — by identity,
    # despite the reversed chronological insertion order.
    assert {by_code["M1"].home_team_name, by_code["M1"].away_team_name} == {"A1", "B2"}
    assert {by_code["M2"].home_team_name, by_code["M2"].away_team_name} == {"B1", "A2"}


@pytest.mark.asyncio
async def test_winners_propagate_to_correct_final_slot(db_session) -> None:
    season_id, t = await _seed(db_session)

    bracket = await TournamentService(db_session).get_bracket(season_id)

    final = next(r for r in bracket.rounds if r.name == "Final")
    m3 = final.matches[0]
    # Final = W1 vs W2 = winner(M1)=A1  vs  winner(M2)=B1.
    assert m3.home_provisional_team_name == "A1"
    assert m3.away_provisional_team_name == "B1"
