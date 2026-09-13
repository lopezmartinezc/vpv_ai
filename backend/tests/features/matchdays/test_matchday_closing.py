"""Closing a jornada: what blocks it, what it does, and what it must never do twice.

Closing marks the matchday finished, moves the season on, **generates the weekly
payments** and awards the achievements. Until this service it was not an action
anyone could take — the scraper did it alone, written out twice, and the copies
had drifted.

The cases below are the ones that cost something when wrong: closing a jornada
that has not finished (the #136 bug, which would have paid out on a matchday
nobody played), paying twice, and touching a season that is closed — the
constraint the user set for this work.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.features.matchdays.closing import MatchdayClosing
from src.shared.models.matchday import Match, Matchday
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.transaction import Transaction


@pytest.fixture
async def scene(db_session):
    """A season on J5, two counting matches, both played and scraped."""
    season = Season(
        name="2026-2027",
        status="active",
        matchday_start=1,
        matchday_current=5,
        matchday_end=38,
        matchday_scanned=4,
        weekly_payments_enabled=True,
    )
    db_session.add(season)
    await db_session.flush()

    home = Team(season_id=season.id, name="Celta", slug="celta")
    away = Team(season_id=season.id, name="Málaga", slug="malaga")
    db_session.add_all([home, away])
    await db_session.flush()

    matchday = Matchday(season_id=season.id, number=5, status="pending")
    db_session.add(matchday)
    await db_session.flush()

    played = [
        Match(
            matchday_id=matchday.id,
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=1,
            away_score=0,
            stats_ok=True,
        ),
        Match(
            matchday_id=matchday.id,
            home_team_id=away.id,
            away_team_id=home.id,
            home_score=2,
            away_score=2,
            stats_ok=True,
        ),
    ]
    db_session.add_all(played)
    await db_session.flush()
    return {"season": season, "matchday": matchday, "matches": played}


async def payments(db_session, matchday_id: int) -> int:
    return await db_session.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.matchday_id == matchday_id)
    )


# --- what blocks it --------------------------------------------------------


async def test_a_match_without_a_result_blocks_the_close(db_session, scene) -> None:
    """The #136 case: an unplayed fixture must not let the jornada pay out."""
    scene["matches"][1].home_score = None
    scene["matches"][1].away_score = None
    await db_session.flush()

    report = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)

    assert not report.closed
    assert any("sin resultado" in b for b in report.blockers)
    assert all(step.outcome == "bloqueado" for step in report.steps)


async def test_a_match_without_stats_blocks_the_close(db_session, scene) -> None:
    scene["matches"][0].stats_ok = False
    await db_session.flush()

    report = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)

    assert not report.closed
    assert any("sin estadísticas" in b for b in report.blockers)


async def test_a_finished_season_is_never_closed(db_session, scene) -> None:
    """The constraint on this work: nothing here may touch a closed season."""
    scene["season"].status = "finished"
    scene["season"].edit_unlocked = False
    await db_session.flush()

    report = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)

    assert not report.closed
    assert any("temporada está cerrada" in b for b in report.blockers)
    await db_session.refresh(scene["matchday"])
    assert scene["matchday"].status == "pending"


async def test_an_unlocked_finished_season_may_be_closed(db_session, scene) -> None:
    """The deliberate escape hatch — an admin unlocking edits — still works."""
    scene["season"].status = "finished"
    scene["season"].edit_unlocked = True
    await db_session.flush()

    report = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)

    assert report.closed


# --- the preview -----------------------------------------------------------


async def test_a_dry_run_writes_absolutely_nothing(db_session, scene) -> None:
    """The whole point of the preview: it must be safe to press."""
    before = await payments(db_session, scene["matchday"].id)

    report = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=True)

    assert report.closed and report.dry_run
    await db_session.refresh(scene["matchday"])
    await db_session.refresh(scene["season"])
    assert scene["matchday"].status == "pending"
    assert scene["matchday"].stats_ok is False
    assert scene["season"].matchday_current == 5
    assert scene["season"].matchday_scanned == 4
    assert await payments(db_session, scene["matchday"].id) == before


async def test_the_preview_lists_the_same_steps_the_close_will_run(db_session, scene) -> None:
    preview = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=True)
    real = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)

    assert [s.name for s in preview.steps] == [s.name for s in real.steps]


# --- what it does ----------------------------------------------------------


async def test_closing_marks_advances_and_records(db_session, scene) -> None:
    report = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)

    assert report.closed and not report.blockers
    await db_session.refresh(scene["matchday"])
    await db_session.refresh(scene["season"])
    assert scene["matchday"].status == "finished"
    assert scene["matchday"].stats_ok is True
    assert scene["season"].matchday_current == 6
    assert scene["season"].matchday_scanned == 5


async def test_closing_twice_does_not_pay_twice(db_session, scene) -> None:
    """Every step is idempotent, and the second report says so rather than
    claiming it did the work again."""
    await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)
    after_first = await payments(db_session, scene["matchday"].id)

    second = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)

    assert second.closed
    assert await payments(db_session, scene["matchday"].id) == after_first
    outcomes = {s.name: s.outcome for s in second.steps}
    assert "hecho" not in [
        outcomes[k] for k in outcomes if "terminada" in k or "estadísticas completas" in k
    ]


async def test_the_last_matchday_of_the_season_does_not_advance_past_the_end(
    db_session, scene
) -> None:
    scene["season"].matchday_current = 5
    scene["season"].matchday_end = 5
    await db_session.flush()

    report = await MatchdayClosing(db_session).close(scene["season"].id, 5, dry_run=False)

    assert report.closed
    await db_session.refresh(scene["season"])
    assert scene["season"].matchday_current == 5


# --- the panel -------------------------------------------------------------


async def test_status_reports_exactly_what_is_missing(db_session, scene) -> None:
    scene["matches"][1].home_score = None
    scene["matches"][1].stats_ok = False
    await db_session.flush()

    state = await MatchdayClosing(db_session).status(scene["season"].id, 5)

    assert state is not None
    assert state.matches_counting == 2
    assert state.matches_without_result == ["Málaga - Celta"]
    assert state.matches_without_stats == ["Málaga - Celta"]
    assert state.is_current is True
    assert not state.can_close


async def test_status_of_a_matchday_that_does_not_exist_is_none(db_session, scene) -> None:
    assert await MatchdayClosing(db_session).status(scene["season"].id, 99) is None
