"""A tag for the player who has barely played and you think will fight for a shirt.

This is the class where the model is most wrong, and measurably so: players
with one or two appearances were projected at 0.33 participation and finished
the season at 0.51. It under-rates them, and the admin watching pre-season
knows something the data does not.

"Competirá" is a claim about MINUTES, not about points per game, so it works
as a floor on expected playing time rather than as a flat bonus — and it is a
role tag, replacing the model's bench-risk guess, which is precisely what the
admin is overriding. Multiplying on top of the floor would count the same
judgement twice, so the role multiplier is neutral.

The floor lands on Prioridad alone. participation, exp_games_remaining and
priority_base are the model's own view of the player, and a tag that rewrote
them would destroy the one thing the Base column is for: seeing what your
judgement changed.
"""

from __future__ import annotations

import pytest

from src.features.stats.service_draft import (
    ALLOWED_TAGS,
    COMPETING_PARTICIPATION,
    ROLE_MULTIPLIER,
    DraftValueService,
)
from src.shared.models.matchday import Matchday
from src.shared.models.season import Season
from src.shared.models.team import Team

from tests.features.stats.test_draft_prep import _prior_player, _roster_player


def test_it_is_an_accepted_role_tag_that_does_not_move_the_value() -> None:
    assert "competira" in ALLOWED_TAGS
    # A role tag, so it replaces the automatic bench-risk discount...
    assert "competira" in ROLE_MULTIPLIER
    # ...and neutral, because the floor below is what carries the judgement.
    assert ROLE_MULTIPLIER["competira"] == 1.00


def test_the_floor_sits_between_the_measurements_it_came_from() -> None:
    """Above the 0.51 that one-or-two-appearance players actually averaged,
    because tagging one is backing him; below the 0.65 of an established
    big-club substitute, because he has not won the shirt yet."""
    assert 0.51 < COMPETING_PARTICIPATION < 0.65


@pytest.fixture
async def board(db_session):
    prior = Season(name="2024-2025", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2025-2026", matchday_start=1, matchday_current=2, matchday_end=38, kind="league"
    )
    db_session.add_all([prior, current])
    await db_session.flush()
    p_team = Team(season_id=prior.id, name="Equipo", slug="equipo")
    c_team = Team(season_id=current.id, name="Equipo", slug="equipo")
    db_session.add_all([p_team, c_team])
    await db_session.flush()
    prior_mds = [Matchday(season_id=prior.id, number=n) for n in range(1, 39)]
    db_session.add_all(prior_mds)
    await db_session.flush()
    # Four of thirty-eight: barely played, and the model's bench-risk flag is on.
    await _prior_player(db_session, prior, p_team, "fringe", "MED", avg=6, mds=prior_mds, games=4)
    _roster_player(db_session, current, c_team, "fringe", "MED")
    # An ever-present, to prove the floor never pulls anyone down.
    await _prior_player(db_session, prior, p_team, "star", "MED", avg=6, mds=prior_mds, games=38)
    _roster_player(db_session, current, c_team, "star", "MED")
    await db_session.flush()

    svc = DraftValueService(db_session)

    async def rows(slug: str, tags: list[str] | None = None):
        board = {p.slug: p for p in (await svc.get_draft_values(current.id)).players}
        if tags is not None:
            await svc.upsert_override(current.id, board[slug].player_id, None, None, tags)
            board = {p.slug: p for p in (await svc.get_draft_values(current.id)).players}
        return board[slug]

    return rows


async def test_it_lifts_the_player_the_model_buries(board) -> None:
    before = await board("fringe")
    assert before.participation is not None and before.participation < COMPETING_PARTICIPATION
    after = await board("fringe", ["competira"])
    assert after.priority > before.priority
    # Lifted to what the floor implies, on top of the bench-risk guess it drops.
    expected = before.priority * (COMPETING_PARTICIPATION / before.participation) / 0.75
    assert after.priority == pytest.approx(expected, rel=1e-2)


async def test_it_does_not_rewrite_the_model_own_figures(board) -> None:
    """participation and exp_games_remaining describe what the model believes.
    Your tag changes the ranking, not the model's mind."""
    before = await board("fringe")
    after = await board("fringe", ["competira"])
    assert after.participation == pytest.approx(before.participation)
    assert after.exp_games_remaining == pytest.approx(before.exp_games_remaining)
    assert after.proj_rest_points == pytest.approx(before.proj_rest_points)


async def test_it_is_a_floor_and_never_pulls_a_starter_down(board) -> None:
    """Tagging someone the model already rates highly must not cost him."""
    before = await board("star")
    assert before.participation is not None and before.participation > COMPETING_PARTICIPATION
    after = await board("star", ["competira"])
    assert after.priority >= before.priority


async def test_it_replaces_the_bench_risk_guess_it_contradicts(board) -> None:
    """Without a role tag the model discounts a bench-risk player by 0.75. The
    tag is the admin saying that guess is wrong, so it must not survive."""
    before = await board("fringe")
    assert before.is_bench_risk is True
    after = await board("fringe", ["competira"])
    # Priority rises by more than the participation floor alone would give,
    # because the 0.75 is gone too.
    floor_only = before.priority * (COMPETING_PARTICIPATION / before.participation)
    assert after.priority > floor_only
    assert after.priority == pytest.approx(floor_only / 0.75, rel=1e-2)


async def test_the_model_view_stays_untouched(board) -> None:
    """priority_base is the model without your tags, and has to stay that way
    or you lose the ability to see what your judgement changed."""
    before = await board("fringe")
    after = await board("fringe", ["competira"])
    assert after.priority_base == pytest.approx(before.priority_base)


async def test_it_cannot_invent_points_for_a_player_with_no_data(db_session) -> None:
    """Participation multiplies a per-game value. A player with no history and
    no current stats has none, so there is nothing for the floor to scale —
    that case needs a manual value, and the tag must not pretend otherwise."""
    season = Season(
        name="2025-2026", matchday_start=1, matchday_current=2, matchday_end=38, kind="league"
    )
    db_session.add(season)
    await db_session.flush()
    team = Team(season_id=season.id, name="Equipo", slug="equipo")
    db_session.add(team)
    await db_session.flush()
    _roster_player(db_session, season, team, "debutante", "DEL")
    await db_session.flush()

    svc = DraftValueService(db_session)
    rows = {p.slug: p for p in (await svc.get_draft_values(season.id)).players}
    await svc.upsert_override(season.id, rows["debutante"].player_id, None, None, ["competira"])
    row = {p.slug: p for p in (await svc.get_draft_values(season.id)).players}["debutante"]
    assert row.tags == ["competira"]
    assert row.proj_rest_points is None
    assert row.priority is None
