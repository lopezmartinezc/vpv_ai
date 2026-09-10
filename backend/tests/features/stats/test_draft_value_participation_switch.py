"""The draft board can be computed with either participation model.

The switch exists so the change is reversible with a click instead of a
revert: ``historico`` is the default and must keep producing exactly what the
board produced before the model existed.

The case that separates them is the cameo man — on for the last ten minutes,
every single week. Counting appearances he is a nailed-on starter; counting
minutes he is the twelfth man. Participation multiplies into
``proj_rest_points``, so getting him wrong costs a whole roster slot.
"""

from __future__ import annotations

import pytest

from src.features.stats.participation import ParticipationModel
from src.features.stats.service_draft import DraftValueService
from src.shared.models.matchday import Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


async def _stats(db, player, matchdays, pts, minutes):
    for md in matchdays:
        db.add(
            PlayerStat(
                player_id=player.id,
                matchday_id=md.id,
                position=player.position,
                played=True,
                minutes_played=minutes,
                pts_total=pts,
                pts_marca_as=0,
            )
        )


@pytest.fixture
async def board(db_session):
    """A club with an ever-present and a cameo man, both half-time regulars
    last season, five matchdays into this one."""

    prior = Season(name="2024-2025", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2025-2026", matchday_start=1, matchday_current=6, matchday_end=38, kind="league"
    )
    db_session.add_all([prior, current])
    await db_session.flush()

    teams = {}
    for s in (prior, current):
        t = Team(season_id=s.id, name="Equipo", slug="equipo")
        db_session.add(t)
        teams[s.id] = t
    await db_session.flush()

    def mk(season, slug):
        p = Player(
            season_id=season.id,
            team_id=teams[season.id].id,
            name=slug,
            display_name=slug,
            slug=slug,
            position="MED",
        )
        db_session.add(p)
        return p

    prior_mds = [Matchday(season_id=prior.id, number=n) for n in range(1, 39)]
    cur_mds = [Matchday(season_id=current.id, number=n) for n in range(1, 6)]
    db_session.add_all(prior_mds + cur_mds)

    players = {slug: (mk(prior, slug), mk(current, slug)) for slug in ("titular", "cameos")}
    await db_session.flush()

    # Both played half of last season, 90 minutes at a time.
    for prev, _ in players.values():
        await _stats(db_session, prev, prior_mds[:19], pts=5, minutes=90)
    # This season: one plays every minute, the other comes on for the last ten.
    await _stats(db_session, players["titular"][1], cur_mds, pts=5, minutes=90)
    await _stats(db_session, players["cameos"][1], cur_mds, pts=5, minutes=10)
    await db_session.flush()

    async def run(model=None):
        svc = DraftValueService(db_session)
        resp = (
            await svc.get_draft_values(current.id)
            if model is None
            else await svc.get_draft_values(current.id, participation_model=model)
        )
        return {p.slug: p for p in resp.players}

    return run


async def test_historico_cannot_tell_the_cameo_man_from_the_starter(board) -> None:
    """Both appeared in all five, so games/matchdays says both play every week."""
    rows = await board(ParticipationModel.HISTORICO)
    assert rows["titular"].participation == pytest.approx(1.0)
    assert rows["cameos"].participation == pytest.approx(1.0)


async def test_mixto_separates_them_on_minutes(board) -> None:
    rows = await board(ParticipationModel.MIXTO)
    assert rows["cameos"].participation < rows["titular"].participation
    # And it costs him real projected matchdays, not a rounding difference.
    assert rows["cameos"].exp_games_remaining < rows["titular"].exp_games_remaining - 5


async def test_the_default_is_the_old_behaviour(board) -> None:
    """Rolling back is choosing the default, so the default must not move."""
    default = await board()
    historico = await board(ParticipationModel.HISTORICO)
    assert {s: p.participation for s, p in default.items()} == {
        s: p.participation for s, p in historico.items()
    }
    assert {s: p.priority for s, p in default.items()} == {
        s: p.priority for s, p in historico.items()
    }


async def test_the_switch_moves_priority_not_just_the_display(board) -> None:
    """Participation feeds proj_rest_points feeds Prioridad — if it did not,
    the toggle would be cosmetic and the whole exercise pointless."""
    historico = await board(ParticipationModel.HISTORICO)
    mixto = await board(ParticipationModel.MIXTO)
    assert mixto["cameos"].priority is not None
    assert mixto["cameos"].priority < historico["cameos"].priority
