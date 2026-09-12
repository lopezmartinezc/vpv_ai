"""The performance table must be able to hide players already taken.

Preparing a draft, the question is nearly always "of the players still free,
who is producing?" — the Draft board can already filter that way, and the
Rendimiento table showed everyone, so the two tabs answered different
questions from the same board.

Ownership lives on players.owner_id, the same source the draft board reads.
"""

from __future__ import annotations

import pytest

from src.features.stats.repository import StatsRepository
from src.shared.models.matchday import Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.participant import SeasonParticipant
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.user import User


@pytest.fixture
async def rows(db_session):
    season = Season(
        name="2026-2027", matchday_start=1, matchday_current=5, matchday_end=38, kind="league"
    )
    db_session.add(season)
    await db_session.flush()
    team = Team(season_id=season.id, name="Getafe", slug="getafe")
    db_session.add(team)
    await db_session.flush()
    md = Matchday(season_id=season.id, number=1, counts=True)
    db_session.add(md)
    await db_session.flush()
    # owner_id is a FK to season_participants, so ownership needs a real one.
    user = User(username="dueno", password_hash="x", display_name="Dueño")
    db_session.add(user)
    await db_session.flush()
    owner = SeasonParticipant(season_id=season.id, user_id=user.id, draft_order=1)
    db_session.add(owner)
    await db_session.flush()

    def mk(slug: str, owner: int | None) -> Player:
        p = Player(
            season_id=season.id,
            team_id=team.id,
            name=slug,
            display_name=slug,
            slug=slug,
            position="DEF",
            owner_id=owner,
        )
        db_session.add(p)
        return p

    taken, free = mk("fichado", owner.id), mk("libre", None)
    await db_session.flush()
    for player in (taken, free):
        db_session.add(
            PlayerStat(
                player_id=player.id,
                matchday_id=md.id,
                position="DEF",
                played=True,
                minutes_played=90,
                pts_total=6,
            )
        )
    await db_session.flush()
    result = await StatsRepository(db_session).get_player_stats(season.id)
    return {r.display_name: r for r in result}


async def test_an_owned_player_is_marked_as_taken(rows) -> None:
    assert rows["fichado"].is_drafted is True


async def test_a_free_player_is_not(rows) -> None:
    assert rows["libre"].is_drafted is False


async def test_both_still_appear_the_flag_filters_nothing_server_side(rows) -> None:
    """Hiding is the table's choice, not the query's: the same response has to
    serve the admin who wants to see everyone."""
    assert set(rows) == {"fichado", "libre"}


async def test_the_aggregates_are_unchanged_by_the_join(rows) -> None:
    """Adding owner_id to the grouping must not split or duplicate a player's
    rows — a silent double-count would be worse than the missing filter."""
    assert rows["fichado"].total_points == 6
    assert rows["fichado"].matchdays_played == 1
