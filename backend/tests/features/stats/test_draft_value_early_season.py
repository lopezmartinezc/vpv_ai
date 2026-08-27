"""get_draft_values must work at the real Liga draft moment (4-8 matchdays).

Before F1 the model returned ZERO players at 4-8 md (HAVING COUNT(*)>=10
excluded the current partial season) and, even if it hadn't, ignored the
current data (is_winter gate at >=10 md). Now it includes current-season
candidates with a low game floor and blends them with the historical prior
via shrinkage; tournament seasons are never used as league history.
"""

from __future__ import annotations

import pytest

from src.features.stats.service_draft import DraftValueService
from src.shared.models.matchday import Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


async def _add_stats(db, player, matchdays, pts, minutes=90, media=0):
    for md in matchdays:
        db.add(
            PlayerStat(
                player_id=player.id,
                matchday_id=md.id,
                position=player.position,
                played=True,
                minutes_played=minutes,
                pts_total=pts,
                pts_marca_as=media,
            )
        )


@pytest.mark.asyncio
async def test_draft_values_blend_at_six_matchdays(db_session) -> None:
    # Prior league season (history) + current league season at md 6.
    prior = Season(name="2024-2025", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2025-2026", matchday_start=1, matchday_current=7, matchday_end=38, kind="league"
    )
    # A tournament season that must NOT be used as league history.
    tourney = Season(name="Mundial 2026", matchday_start=1, matchday_current=8, kind="tournament")
    db_session.add_all([prior, current, tourney])
    await db_session.flush()

    teams = {}
    for s in (prior, current, tourney):
        t = Team(season_id=s.id, name="Equipo", slug="equipo")
        db_session.add(t)
        teams[s.id] = t
    await db_session.flush()

    def mk_player(season, slug, pos="MED"):
        p = Player(
            season_id=season.id,
            team_id=teams[season.id].id,
            name=slug,
            display_name=slug,
            slug=slug,
            position=pos,
        )
        db_session.add(p)
        return p

    # Matchdays
    prior_mds = [Matchday(season_id=prior.id, number=n) for n in range(1, 11)]
    cur_mds = [Matchday(season_id=current.id, number=n) for n in range(1, 7)]
    tour_mds = [Matchday(season_id=tourney.id, number=n) for n in range(1, 7)]
    db_session.add_all(prior_mds + cur_mds + tour_mds)

    # "star": strong history (8.0), weak current (2.0) over 6 games.
    star_prev = mk_player(prior, "star")
    star_cur = mk_player(current, "star")
    # "rookie": only current season, 4 games at 5.0 (no history).
    rookie = mk_player(current, "rookie")
    # "fringe": 1 current game — below the 2-game candidate floor.
    fringe = mk_player(current, "fringe")
    # tournament player sharing star's slug — must be ignored as history.
    mk_player(tourney, "star")
    await db_session.flush()

    await _add_stats(db_session, star_prev, prior_mds, pts=8)
    await _add_stats(db_session, star_cur, cur_mds, pts=2, media=1)  # half from Marca/AS
    await _add_stats(db_session, rookie, cur_mds[:4], pts=5)
    await _add_stats(db_session, fringe, cur_mds[:1], pts=9)
    await db_session.flush()

    resp = await DraftValueService(db_session).get_draft_values(current.id)

    by_slug = {p.slug: p for p in resp.players}
    # Roster-seeded: everyone in the season appears. fringe (1 game < min, no
    # history) shows flagged new with no projection instead of being dropped.
    assert "star" in by_slug and "rookie" in by_slug
    assert "fringe" in by_slug
    fringe_row = by_slug["fringe"]
    assert fringe_row.is_new is True
    assert fringe_row.auto_projection is None
    assert fringe_row.effective_value is None
    assert fringe_row.vorp is None

    star = by_slug["star"]
    # Shrinkage weight on current = 6 / (6 + 4) = 0.6.
    assert star.weight_current == pytest.approx(0.6, abs=1e-9)
    # Blended between the weak current (2.0) and the strong career prior.
    assert 2.0 < star.ensemble_score < 8.0
    # History from the prior LEAGUE season only (tournament ignored) => 2 seasons.
    assert star.seasons_played == 2

    rookie_row = by_slug["rookie"]
    # No history -> shrink toward the newcomer prior (weight 4/(4+4)=0.5).
    assert rookie_row.weight_current == pytest.approx(0.5)
    # Rookie's current avg is 5.0 == the prior, so the blend still lands on 5.0.
    assert rookie_row.ensemble_score == pytest.approx(5.0, abs=1e-6)
    assert rookie_row.seasons_played == 1

    assert resp.matchdays_played == 6

    # Draft board: players WITH a value get a VORP + position rank; the board
    # is sorted by VORP (no-value players last). star & rookie are MED, so the
    # weaker one is replacement (VORP 0) and the stronger one's is positive.
    valued = [p for p in resp.players if p.effective_value is not None]
    assert all(p.vorp is not None and p.position_rank is not None for p in valued)
    assert resp.players == sorted(
        resp.players,
        key=lambda p: (p.vorp if p.vorp is not None else -1e9, p.ensemble_score),
        reverse=True,
    )
    med = [p for p in valued if p.position == "MED"]
    assert min(p.vorp for p in med) == pytest.approx(0.0)
    assert max(p.vorp for p in med) > 0

    # F2 — reliability: rookie is pure events (event_share 1.0); star has some
    # Marca/AS points, so its share is below 1.
    assert rookie_row.event_share == pytest.approx(1.0)
    assert star.event_share is not None and star.event_share < 1.0
    # F2 — durability: 38 - 7 = 31 matchdays left, availability 1.0 (all
    # starts), so ~31 expected games and a positive rest-of-season projection.
    assert star.exp_games_remaining == pytest.approx(31.0)
    assert star.proj_rest_points == pytest.approx(star.ensemble_score * 31.0, abs=0.2)
