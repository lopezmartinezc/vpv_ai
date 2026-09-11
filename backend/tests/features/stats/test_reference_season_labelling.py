"""Say WHICH season the raw production figures describe, and show the previous one.

The expanded row lists Partidos, Pts totales, Goles, Asistencias and the
Marca/AS marks. They all come from the "reference season", which flips to the
CURRENT one as soon as it has a couple of appearances. Five matchdays into a
season that means a proven scorer reads "Goles: 0" — true of those five
matchdays, and the opposite of what someone preparing a draft concludes.

Two things fix it: name the season the numbers belong to, and carry the
previous one alongside, because at draft time the comparison IS the decision.
"""

from __future__ import annotations

import pytest

from src.features.stats.service_draft import DraftValueService
from src.shared.models.matchday import Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


async def _stats(db, player, matchdays, *, pts, goals=0, assists=0):
    for i, md in enumerate(matchdays):
        db.add(
            PlayerStat(
                player_id=player.id,
                matchday_id=md.id,
                position=player.position,
                played=True,
                minutes_played=90,
                pts_total=pts,
                goals=goals if i == 0 else 0,
                assists=assists if i == 0 else 0,
            )
        )


@pytest.fixture
async def board(db_session):
    """A scorer with a big prior season and a quiet start to this one."""
    prior = Season(name="2025-2026", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2026-2027", matchday_start=6, matchday_current=5, matchday_end=38, kind="league"
    )
    db_session.add_all([prior, current])
    await db_session.flush()
    teams = {}
    for s in (prior, current):
        t = Team(season_id=s.id, name="Betis", slug="betis")
        db_session.add(t)
        teams[s.id] = t
    await db_session.flush()
    prior_mds = [Matchday(season_id=prior.id, number=n) for n in range(1, 31)]
    cur_mds = [Matchday(season_id=current.id, number=n) for n in range(1, 6)]
    db_session.add_all(prior_mds + cur_mds)
    await db_session.flush()

    def mk(season, slug):
        p = Player(
            season_id=season.id,
            team_id=teams[season.id].id,
            name=slug,
            display_name=slug,
            slug=slug,
            position="DEL",
        )
        db_session.add(p)
        return p

    scorer_prev, scorer_now = mk(prior, "cucho"), mk(current, "cucho")
    rookie = mk(current, "debutante")
    await db_session.flush()
    # 12 goals last season; none in the five matchdays played so far.
    await _stats(db_session, scorer_prev, prior_mds, pts=7, goals=12, assists=5)
    await _stats(db_session, scorer_now, cur_mds, pts=4, goals=0, assists=0)
    await _stats(db_session, rookie, cur_mds, pts=3, goals=1)
    await db_session.flush()

    rows = {
        p.slug: p
        for p in (await DraftValueService(db_session).get_draft_values(current.id)).players
    }
    return rows


def test_the_figures_say_which_season_they_describe(board) -> None:
    assert board["cucho"].ref_season_name == "2026-2027"


def test_the_previous_season_travels_alongside(board) -> None:
    """The number the drafter is actually looking for."""
    previous = board["cucho"].previous_season
    assert previous is not None
    assert previous.season_name == "2025-2026"
    assert previous.goals == 12
    assert previous.assists == 5
    assert previous.games_played == 30


def test_the_current_figures_are_unchanged_by_this(board) -> None:
    """Still this season's — the fix is labelling and context, not a rewrite."""
    assert board["cucho"].goals == 0
    assert board["cucho"].games_played == 5


def test_a_player_with_no_past_carries_none_rather_than_zeros(board) -> None:
    """Zeros would read as 'scored nothing last year' instead of 'no last year'."""
    assert board["debutante"].previous_season is None
    assert board["debutante"].ref_season_name == "2026-2027"


@pytest.mark.asyncio
async def test_preseason_labels_the_season_it_falls_back_to(db_session) -> None:
    """With no current data at all the figures come from last season, and the
    label has to say so rather than naming the season on the calendar."""
    prior = Season(name="2025-2026", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2026-2027", matchday_start=1, matchday_current=0, matchday_end=38, kind="league"
    )
    db_session.add_all([prior, current])
    await db_session.flush()
    teams = {}
    for s in (prior, current):
        t = Team(season_id=s.id, name="Betis", slug="betis")
        db_session.add(t)
        teams[s.id] = t
    await db_session.flush()
    mds = [Matchday(season_id=prior.id, number=n) for n in range(1, 31)]
    db_session.add_all(mds)
    await db_session.flush()

    def mk(season):
        p = Player(
            season_id=season.id,
            team_id=teams[season.id].id,
            name="cucho",
            display_name="cucho",
            slug="cucho",
            position="DEL",
        )
        db_session.add(p)
        return p

    prev_player = mk(prior)
    mk(current)
    await db_session.flush()
    await _stats(db_session, prev_player, mds, pts=7, goals=12)
    await db_session.flush()

    rows = {
        p.slug: p
        for p in (await DraftValueService(db_session).get_draft_values(current.id)).players
    }
    assert rows["cucho"].ref_season_name == "2025-2026"
    assert rows["cucho"].goals == 12
    # No second line to show: the figures already are last season's.
    assert rows["cucho"].previous_season is None
