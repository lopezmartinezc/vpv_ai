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
from src.shared.models.matchday import Match, Matchday
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
        season_id=last.id,
        team_id=teams[last.id].id,
        name="pen",
        display_name="pen",
        slug="pen",
        position="DEL",
    )
    db_session.add(pen)
    await db_session.flush()
    for md in l_mds:
        db_session.add(
            PlayerStat(
                player_id=pen.id,
                matchday_id=md.id,
                position="DEL",
                played=True,
                minutes_played=90,
                pts_total=5,
                penalty_goals=1,
            )
        )
    # roster rows for current season.
    _roster_player(db_session, current, teams[current.id], "peaker", "MED")
    db_session.add(
        Player(
            season_id=current.id,
            team_id=teams[current.id].id,
            name="pen",
            display_name="pen",
            slug="pen",
            position="DEL",
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
    # No-history + current: shrinks toward the newcomer prior (not full weight).
    out2 = project_value(hist=[], current=_ps(5.0))
    assert out2.weight_current == pytest.approx(10 / 14)  # games 10, k 4
    # avg == prior (5.0) here, so the blend still lands on 5.0.
    assert out2.ensemble_score == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_deactivated_players_excluded_from_board(db_session) -> None:
    """A player who left the league (is_available=False, soft-deactivated by
    sync-rosters) must NOT appear on the draft board."""
    season = Season(
        name="2026-2027", matchday_start=4, matchday_current=1, matchday_end=38, kind="league"
    )
    db_session.add(season)
    await db_session.flush()
    team = Team(season_id=season.id, name="Alfa", slug="alfa")
    db_session.add(team)
    await db_session.flush()

    here = Player(
        season_id=season.id,
        team_id=team.id,
        name="here",
        display_name="here",
        slug="here",
        position="DEL",
        is_available=True,
    )
    gone = Player(
        season_id=season.id,
        team_id=team.id,
        name="gone",
        display_name="gone",
        slug="gone",
        position="DEL",
        is_available=False,
    )
    db_session.add_all([here, gone])
    await db_session.flush()

    resp = await DraftValueService(db_session).get_draft_values(season.id)
    slugs = {p.slug for p in resp.players}
    assert "here" in slugs
    assert "gone" not in slugs


@pytest.mark.asyncio
async def test_bench_risk_uses_history_not_partial_current(db_session) -> None:
    """An established starter (full last season) must NOT be flagged bench risk
    just because the current season only has 1-2 matchdays scraped."""
    last = Season(name="2025-2026", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2026-2027", matchday_start=1, matchday_current=2, matchday_end=38, kind="league"
    )
    db_session.add_all([last, current])
    await db_session.flush()
    t_last = Team(season_id=last.id, name="Getafe", slug="getafe")
    t_cur = Team(season_id=current.id, name="Getafe", slug="getafe")
    db_session.add_all([t_last, t_cur])
    await db_session.flush()

    # Last season: durable keeper, played 23 games (>= 22, full availability).
    last_mds = [Matchday(season_id=last.id, number=n) for n in range(1, 24)]
    db_session.add_all(last_mds)
    await db_session.flush()
    soria_last = Player(
        season_id=last.id,
        team_id=t_last.id,
        name="soria",
        display_name="Soria",
        slug="soria",
        position="POR",
    )
    db_session.add(soria_last)
    await db_session.flush()
    for md in last_mds:
        db_session.add(
            PlayerStat(
                player_id=soria_last.id,
                matchday_id=md.id,
                position="POR",
                played=True,
                minutes_played=90,
                pts_total=5,
            )
        )

    # Current season: roster row + a single scraped matchday (1 game).
    soria_cur = Player(
        season_id=current.id,
        team_id=t_cur.id,
        name="soria",
        display_name="Soria",
        slug="soria",
        position="POR",
        is_available=True,
    )
    md_cur = Matchday(season_id=current.id, number=1, counts=True)
    db_session.add_all([soria_cur, md_cur])
    await db_session.flush()
    db_session.add(
        PlayerStat(
            player_id=soria_cur.id,
            matchday_id=md_cur.id,
            position="POR",
            played=True,
            minutes_played=90,
            pts_total=6,
        )
    )
    await db_session.flush()

    resp = await DraftValueService(db_session).get_draft_values(current.id)
    soria = {p.slug: p for p in resp.players}["soria"]
    assert soria.is_bench_risk is False  # durable last season, not a bench risk


@pytest.mark.asyncio
async def test_nonplayed_rows_do_not_dilute(db_session) -> None:
    """player_stats rows for games the player did NOT play (played=False,
    0 min, 0 pts) must not count: they'd deflate avg_pts and availability and
    falsely flag a nailed starter as bench risk."""
    season = Season(
        name="2026-2027", matchday_start=1, matchday_current=16, matchday_end=38, kind="league"
    )
    db_session.add(season)
    await db_session.flush()
    team = Team(season_id=season.id, name="Alfa", slug="alfa")
    db_session.add(team)
    await db_session.flush()
    star = Player(
        season_id=season.id,
        team_id=team.id,
        name="star",
        display_name="Star",
        slug="star",
        position="DEL",
        is_available=True,
    )
    mds = [Matchday(season_id=season.id, number=n, counts=True) for n in range(1, 16)]
    db_session.add_all([star, *mds])
    await db_session.flush()

    # 10 games actually played (8 pts, full match) + 5 he did not play.
    for i, md in enumerate(mds):
        played = i < 10
        db_session.add(
            PlayerStat(
                player_id=star.id,
                matchday_id=md.id,
                position="DEL",
                played=played,
                minutes_played=90 if played else 0,
                pts_total=8 if played else 0,
            )
        )
    await db_session.flush()

    resp = await DraftValueService(db_session).get_draft_values(season.id, min_games=2)
    star_row = {p.slug: p for p in resp.players}["star"]
    # avg over the 10 PLAYED games = 8.0, not 8*10/15 = 5.33.
    assert star_row.avg_points == pytest.approx(8.0)
    # Started every game he featured in → full availability, not 10/15.
    assert star_row.availability == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_priority_is_master_sort_and_risk_discounted(db_session) -> None:
    """Board is ordered by `priority` (risk-adjusted projected total), and the
    discount actually lowers it below the raw projection."""
    current = await _setup(db_session)
    resp = await DraftValueService(db_session).get_draft_values(current.id)

    ranked = [p for p in resp.players if p.priority is not None]
    assert ranked, "expected players with a priority"
    # Results come back sorted by priority descending.
    prios = [p.priority for p in ranked]
    assert prios == sorted(prios, reverse=True)
    # overall_rank follows priority order (1-based).
    assert ranked[0].overall_rank == 1
    # A flagged player's priority is strictly below its raw projected total.
    for p in ranked:
        if (p.is_bench_risk or p.is_peak_year) and p.proj_rest_points:
            assert p.priority < p.proj_rest_points


@pytest.mark.asyncio
async def test_keeper_valued_by_team_defense(db_session) -> None:
    """Keepers carry the defensive strength of their team, promoted teams get a
    neutral prior, and a keeper who moved to a stronger defense is nudged up."""
    prior = Season(name="2025-2026", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2026-2027", matchday_start=1, matchday_current=2, matchday_end=38, kind="league"
    )
    db_session.add_all([prior, current])
    await db_session.flush()
    p_fort = Team(season_id=prior.id, name="Fortress", slug="fortress")  # concedes 0
    p_siev = Team(season_id=prior.id, name="Sieve", slug="sieve")  # concedes 2
    db_session.add_all([p_fort, p_siev])
    await db_session.flush()
    mds = [Matchday(season_id=prior.id, number=n, counts=True) for n in range(1, 7)]
    db_session.add_all(mds)
    await db_session.flush()
    for md in mds:  # Fortress 2-0 Sieve every week
        db_session.add(
            Match(
                matchday_id=md.id,
                home_team_id=p_fort.id,
                away_team_id=p_siev.id,
                home_score=2,
                away_score=0,
                counts=True,
            )
        )
    # Two keepers, identical history at the weak-defense club (Sieve, avg 5).
    for slug in ("mover", "stayer"):
        kp = Player(
            season_id=prior.id,
            team_id=p_siev.id,
            name=slug,
            display_name=slug,
            slug=slug,
            position="POR",
        )
        db_session.add(kp)
        await db_session.flush()
        for md in mds:
            db_session.add(
                PlayerStat(
                    player_id=kp.id,
                    matchday_id=md.id,
                    position="POR",
                    played=True,
                    minutes_played=90,
                    pts_total=5,
                )
            )
    # Current rosters: 'mover' -> Fortress (strong D), 'stayer' -> Sieve, plus a
    # promoted-team player whose club wasn't in La Liga last season.
    c_fort = Team(season_id=current.id, name="Fortress", slug="fortress")
    c_siev = Team(season_id=current.id, name="Sieve", slug="sieve")
    c_promo = Team(season_id=current.id, name="Promoted", slug="promoted")
    db_session.add_all([c_fort, c_siev, c_promo])
    await db_session.flush()
    db_session.add_all(
        [
            Player(
                season_id=current.id,
                team_id=c_fort.id,
                name="mover",
                display_name="mover",
                slug="mover",
                position="POR",
                is_available=True,
            ),
            Player(
                season_id=current.id,
                team_id=c_siev.id,
                name="stayer",
                display_name="stayer",
                slug="stayer",
                position="POR",
                is_available=True,
            ),
            Player(
                season_id=current.id,
                team_id=c_promo.id,
                name="promo",
                display_name="promo",
                slug="promo",
                position="DEF",
                is_available=True,
            ),
        ]
    )
    await db_session.flush()

    resp = await DraftValueService(db_session).get_draft_values(current.id)
    by = {p.slug: p for p in resp.players}
    # Team defense attached: Fortress concedes 0, Sieve 2, promoted -> league avg (1.0).
    assert by["mover"].team_goals_conceded == pytest.approx(0.0)
    assert by["stayer"].team_goals_conceded == pytest.approx(2.0)
    assert by["promo"].team_goals_conceded == pytest.approx(1.0)
    # Same history, but the keeper who moved to a stronger defense is valued higher.
    assert by["mover"].auto_projection > by["stayer"].auto_projection


@pytest.mark.asyncio
async def test_tags_adjust_priority(db_session) -> None:
    """Admin tags multiply the draft Priority; 'titular' cancels the bench-risk
    discount; unknown tags are dropped and known ones round-trip."""
    prior = Season(name="2025-2026", matchday_start=1, matchday_current=38, kind="league")
    current = Season(
        name="2026-2027", matchday_start=1, matchday_current=1, matchday_end=38, kind="league"
    )
    db_session.add_all([prior, current])
    await db_session.flush()
    p_team = Team(season_id=prior.id, name="A", slug="a")
    c_team = Team(season_id=current.id, name="A", slug="a")
    db_session.add_all([p_team, c_team])
    await db_session.flush()
    prior_mds = [Matchday(season_id=prior.id, number=n) for n in range(1, 11)]
    db_session.add_all(prior_mds)
    await db_session.flush()
    # 10 games last season (< 22) → is_bench_risk True → baseline priority x0.75.
    await _prior_player(db_session, prior, p_team, "star", "MED", avg=6, mds=prior_mds)
    _roster_player(db_session, current, c_team, "star", "MED")
    await db_session.flush()

    svc = DraftValueService(db_session)
    base = {p.slug: p for p in (await svc.get_draft_values(current.id)).players}["star"]
    base_prio = base.priority
    assert base.is_bench_risk is True and base_prio is not None
    pid = base.player_id

    async def prio_with(tags: list[str]) -> float:
        await svc.upsert_override(current.id, pid, None, None, tags)
        row = {p.slug: p for p in (await svc.get_draft_values(current.id)).players}["star"]
        assert row.tags == [t for t in tags if t in {"titular", "evitar", "objetivo"}]
        assert row.priority is not None
        return row.priority

    # evitar x0.40 (bench discount still applies) → lower.
    assert await prio_with(["evitar"]) == pytest.approx(base_prio * 0.40, rel=1e-3)
    # objetivo x1.20 → higher.
    assert await prio_with(["objetivo"]) == pytest.approx(base_prio * 1.20, rel=1e-3)
    # titular cancels the x0.75 bench discount → priority goes up ~1/0.75.
    assert await prio_with(["titular"]) == pytest.approx(base_prio / 0.75, rel=1e-3)
    # unknown tag is dropped (round-trips empty).
    await svc.upsert_override(current.id, pid, None, None, ["bogus"])
    row = {p.slug: p for p in (await svc.get_draft_values(current.id)).players}["star"]
    assert row.tags == []
