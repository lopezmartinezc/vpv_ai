"""Preseason draft board: roster-seeded, history projection, flags, overrides.

Before this, the draft board was empty preseason (it keyed off current-season
player_stats, which don't exist at 0 matchdays). Now it seeds from the roster,
projects returning players from history, flags new/role-changed players, and
lets an admin set a manual value that drives the effective value + VORP.
"""

from __future__ import annotations

import pytest

from src.features.stats.service_draft import (
    DraftValueService,
    _PlayerSeason,
    project_value,
)
from src.shared.models.matchday import Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


async def _prior_player(db, season, team, slug, pos, avg, mds, games=10):
    """A player with prior-season stats (history)."""
    p = Player(
        season_id=season.id,
        team_id=team.id,
        name=slug,
        display_name=slug,
        slug=slug,
        position=pos,
    )
    db.add(p)
    await db.flush()
    for md in mds[:games]:
        db.add(
            PlayerStat(
                player_id=p.id,
                matchday_id=md.id,
                position=pos,
                played=True,
                minutes_played=90,
                pts_total=avg,
            )
        )
    return p


def _roster_player(db, season, team, slug, pos):
    """A current-season roster row (no stats)."""
    p = Player(
        season_id=season.id,
        team_id=team.id,
        name=slug,
        display_name=slug,
        slug=slug,
        position=pos,
    )
    db.add(p)
    return p


async def _setup(db):
    prior = Season(name="2025-2026", matchday_start=1, matchday_current=38, kind="league")
    # Current season in PRESEASON: 0 matchdays played, no player_stats.
    current = Season(
        name="2026-2027", matchday_start=1, matchday_current=1, matchday_end=38, kind="league"
    )
    db.add_all([prior, current])
    await db.flush()

    p_alfa = Team(season_id=prior.id, name="Alfa", slug="alfa")
    p_gamma = Team(season_id=prior.id, name="Gamma", slug="gamma")
    c_alfa = Team(season_id=current.id, name="Alfa", slug="alfa")
    c_beta = Team(season_id=current.id, name="Beta", slug="beta")
    db.add_all([p_alfa, p_gamma, c_alfa, c_beta])
    await db.flush()

    prior_mds = [Matchday(season_id=prior.id, number=n) for n in range(1, 11)]
    db.add_all(prior_mds)
    await db.flush()

    # History (prior season).
    await _prior_player(db, prior, p_alfa, "vet", "MED", avg=6, mds=prior_mds)
    await _prior_player(db, prior, p_alfa, "steady", "MED", avg=4, mds=prior_mds)
    await _prior_player(db, prior, p_alfa, "poschange", "DEF", avg=5, mds=prior_mds)

    # Current roster (no stats). vet moved Alfa->Beta; poschange DEF->MED; rookie new.
    _roster_player(db, current, c_beta, "vet", "MED")
    _roster_player(db, current, c_alfa, "steady", "MED")
    _roster_player(db, current, c_alfa, "poschange", "MED")
    _roster_player(db, current, c_alfa, "rookie", "MED")
    await db.flush()
    return current


@pytest.mark.asyncio
async def test_preseason_projects_from_history_and_flags_new(db_session) -> None:
    current = await _setup(db_session)
    resp = await DraftValueService(db_session).get_draft_values(current.id)

    by_slug = {p.slug: p for p in resp.players}
    # All roster players appear even at 0 matchdays.
    assert set(by_slug) == {"vet", "steady", "poschange", "rookie"}

    vet = by_slug["vet"]
    # History-only cold-start projection: weight on current = 0, ensemble ~6.
    assert vet.weight_current == pytest.approx(0.0)
    assert vet.auto_projection is not None and vet.auto_projection > 4.0
    assert vet.effective_value == vet.auto_projection
    assert vet.vorp is not None

    rookie = by_slug["rookie"]
    assert rookie.is_new is True
    assert rookie.auto_projection is None
    assert rookie.effective_value is None
    assert rookie.vorp is None


@pytest.mark.asyncio
async def test_role_change_flags(db_session) -> None:
    current = await _setup(db_session)
    resp = await DraftValueService(db_session).get_draft_values(current.id)
    by_slug = {p.slug: p for p in resp.players}

    assert by_slug["vet"].team_changed is True  # Alfa -> Beta
    assert by_slug["vet"].position_changed is False
    assert by_slug["poschange"].position_changed is True  # DEF -> MED
    assert by_slug["poschange"].team_changed is False
    assert by_slug["steady"].team_changed is False
    assert by_slug["steady"].position_changed is False
    assert by_slug["steady"].is_new is False
    assert by_slug["rookie"].is_new is True


@pytest.mark.asyncio
async def test_manual_override_drives_effective_value_and_vorp(db_session) -> None:
    current = await _setup(db_session)
    svc = DraftValueService(db_session)

    # rookie has no projection; give it a strong manual value.
    resp = await svc.get_draft_values(current.id)
    rookie_id = next(p.player_id for p in resp.players if p.slug == "rookie")
    await svc.upsert_override(current.id, rookie_id, manual_value=9.0, note="fichaje estrella")

    resp2 = await svc.get_draft_values(current.id)
    rookie = next(p for p in resp2.players if p.slug == "rookie")
    assert rookie.manual_value == pytest.approx(9.0)
    assert rookie.note == "fichaje estrella"
    assert rookie.effective_value == pytest.approx(9.0)
    assert rookie.vorp is not None  # now ranks
    # With value 9 (top of the MED pool) it should be the #1 MED by VORP.
    med = [p for p in resp2.players if p.position == "MED" and p.vorp is not None]
    assert max(med, key=lambda p: p.vorp).slug == "rookie"


@pytest.mark.asyncio
async def test_risk_flags(db_session) -> None:
    older = Season(name="2024-2025", matchday_start=1, matchday_current=38, kind="league")
    last = Season(name="2025-2026", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2026-2027", matchday_start=1, matchday_current=1, matchday_end=38, kind="league"
    )
    db_session.add_all([older, last, current])
    await db_session.flush()
    teams = {}
    for s in (older, last, current):
        t = Team(season_id=s.id, name="Alfa", slug="alfa")
        db_session.add(t)
        teams[s.id] = t
    await db_session.flush()
    o_mds = [Matchday(season_id=older.id, number=n) for n in range(1, 11)]
    l_mds = [Matchday(season_id=last.id, number=n) for n in range(1, 11)]
    db_session.add_all(o_mds + l_mds)
    await db_session.flush()

    # peaker: MED, older avg 3, last avg 6 -> last well above career -> peak year.
    await _prior_player(db_session, older, teams[older.id], "peaker", "MED", avg=3, mds=o_mds)
    await _prior_player(db_session, last, teams[last.id], "peaker", "MED", avg=6, mds=l_mds)
    # pen: DEL who took penalties last season.
    pen = Player(
        season_id=last.id, team_id=teams[last.id].id, name="pen", display_name="pen",
        slug="pen", position="DEL",
    )
    db_session.add(pen)
    await db_session.flush()
    for md in l_mds:
        db_session.add(
            PlayerStat(
                player_id=pen.id, matchday_id=md.id, position="DEL",
                played=True, minutes_played=90, pts_total=5, penalty_goals=1,
            )
        )
    # roster rows for current season.
    _roster_player(db_session, current, teams[current.id], "peaker", "MED")
    db_session.add(
        Player(
            season_id=current.id, team_id=teams[current.id].id, name="pen",
            display_name="pen", slug="pen", position="DEL",
        )
    )
    await db_session.flush()

    resp = await DraftValueService(db_session).get_draft_values(current.id)
    by_slug = {p.slug: p for p in resp.players}
    assert by_slug["peaker"].is_peak_year is True
    assert by_slug["pen"].is_penalty_taker is True
    # Both played only 10 games last season -> flagged bench risk (<22 games).
    assert by_slug["pen"].is_bench_risk is True


def _ps(avg, games=10, minutes=900) -> _PlayerSeason:
    return _PlayerSeason(
        slug="p",
        display_name="P",
        position="MED",
        season_id=1,
        season_name="s",
        games=games,
        games_45min=games,
        avg_pts=avg,
        total_pts=avg * games,
        std_pts=1.0,
        media_pts=0.0,
        marca_avg=None,
        as_avg=None,
        goals=0,
        assists=0,
        minutes=minutes,
        second_half_avg=0.0,
        team_name="T",
        photo_path=None,
        player_id=1,
        penalty_goals=0,
        penalties_missed=0,
    )


def test_project_value_none_current_is_history_only() -> None:
    hist = [_ps(6.0), _ps(6.0)]
    out = project_value(hist=hist, current=None)
    assert out.weight_current == 0.0
    assert out.ensemble_score == pytest.approx(out.career_ensemble)
    # And no-history + current still works (weight 1.0).
    out2 = project_value(hist=[], current=_ps(5.0))
    assert out2.weight_current == 1.0
    assert out2.ensemble_score == pytest.approx(5.0)
