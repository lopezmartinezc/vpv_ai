"""The 🍔 ranking must not charge a manager for goals in a postponed fixture.

It filtered matchdays.counts but not matches.counts, against the project's own
rule for anything that scores. A goal in a fixture marked as not counting —
postponed, friendly — inside a counting jornada was charged to the manager who
left the scorer out, as if it had counted.

The match is LEFT-joined on purpose: rows migrated from the old site can carry
no match_id, and those must keep counting exactly as before. Only a fixture
known not to count drops out.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.burger_ranking.service import BurgerRankingService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.user import User


@pytest.fixture
async def ranking(db_session: AsyncSession):
    """One manager, three scorers he left out, in one counting jornada:
    one in a counting fixture, one in a postponed fixture, one migrated
    without a match_id."""
    season = Season(name="2025-2026", status="active", matchday_start=1, matchday_end=38)
    db_session.add(season)
    await db_session.flush()
    user = User(username="manager", display_name="Manager", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    manager = SeasonParticipant(season_id=season.id, user_id=user.id)
    db_session.add(manager)
    await db_session.flush()

    teams = [Team(season_id=season.id, name=n, slug=n.lower()) for n in ("A", "B", "C", "D")]
    db_session.add_all(teams)
    await db_session.flush()
    jornada = Matchday(season_id=season.id, number=1, counts=True)
    db_session.add(jornada)
    await db_session.flush()
    counting = Match(
        matchday_id=jornada.id, home_team_id=teams[0].id, away_team_id=teams[1].id, counts=True
    )
    postponed = Match(
        matchday_id=jornada.id, home_team_id=teams[2].id, away_team_id=teams[3].id, counts=False
    )
    db_session.add_all([counting, postponed])
    await db_session.flush()

    def scorer(name: str, team: Team) -> Player:
        return Player(
            season_id=season.id,
            team_id=team.id,
            name=name,
            display_name=name,
            slug=name.lower(),
            position="DEL",
            owner_id=manager.id,
        )

    in_counting, in_postponed, migrated = (
        scorer("Cuenta", teams[0]),
        scorer("Aplazado", teams[2]),
        scorer("Migrado", teams[1]),
    )
    db_session.add_all([in_counting, in_postponed, migrated])
    await db_session.flush()
    db_session.add_all(
        [
            PlayerStat(
                player_id=in_counting.id,
                matchday_id=jornada.id,
                match_id=counting.id,
                position="DEL",
                played=True,
                goals=1,
            ),
            PlayerStat(
                player_id=in_postponed.id,
                matchday_id=jornada.id,
                match_id=postponed.id,
                position="DEL",
                played=True,
                goals=2,
            ),
            PlayerStat(
                player_id=migrated.id,
                matchday_id=jornada.id,
                match_id=None,
                position="DEL",
                played=True,
                goals=1,
            ),
        ]
    )
    await db_session.flush()
    return await BurgerRankingService(db_session).get_ranking(season.id)


async def test_a_goal_in_a_postponed_fixture_is_not_charged(ranking) -> None:
    [entry] = ranking.entries
    assert "Aplazado" not in {g.player_name for g in entry.goals}


async def test_a_goal_in_a_counting_fixture_still_is(ranking) -> None:
    [entry] = ranking.entries
    assert "Cuenta" in {g.player_name for g in entry.goals}


async def test_a_migrated_row_without_a_match_keeps_counting(ranking) -> None:
    """The LEFT join: history that never had a match_id must not vanish."""
    [entry] = ranking.entries
    assert "Migrado" in {g.player_name for g in entry.goals}
    assert entry.total == 2
