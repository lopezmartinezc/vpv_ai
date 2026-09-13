"""A match that has not been played must never be marked as having its stats in.

Production, season 2026-2027, jornada 5 — two fixtures kicking off later that
day, neither with a score, both already `stats_ok = TRUE`. Jornada 7, a week
away, had five of its ten marked the same way:

    Celta  - Málaga     (13/09 14:00)   sin resultado   stats_ok = t
    Getafe - Deportivo  (13/09 18:30)   sin resultado   stats_ok = t

The four callers mark a match done on "no errors and at least one player
processed", and futbolfantasy publishes squads and probable line-ups days
before kick-off. Those parse into valid rows of zero minutes, so an unplayed
fixture clears that bar.

It matters because `stats_ok` on every counting match is what closes a
matchday, and closing one advances `matchday_current`, generates the weekly
payments and evaluates achievements. So the guard sits at the single
repository method all four callers go through, and the gate is the score.
"""

from __future__ import annotations

import pytest

from src.features.scraping.repository import ScrapingRepository
from src.shared.models.matchday import Match, Matchday
from src.shared.models.season import Season
from src.shared.models.team import Team


@pytest.fixture
async def fixtures(db_session):
    season = Season(name="2026-2027", status="active", matchday_start=6, matchday_end=38)
    db_session.add(season)
    await db_session.flush()

    home = Team(season_id=season.id, name="Celta", slug="celta")
    away = Team(season_id=season.id, name="Málaga", slug="malaga")
    db_session.add_all([home, away])
    await db_session.flush()

    matchday = Matchday(season_id=season.id, number=5)
    db_session.add(matchday)
    await db_session.flush()

    unplayed = Match(matchday_id=matchday.id, home_team_id=home.id, away_team_id=away.id)
    played = Match(
        matchday_id=matchday.id,
        home_team_id=away.id,
        away_team_id=home.id,
        home_score=2,
        away_score=1,
    )
    db_session.add_all([unplayed, played])
    await db_session.flush()
    return {"unplayed": unplayed, "played": played}


async def test_a_match_with_no_result_is_refused(db_session, fixtures) -> None:
    repo = ScrapingRepository(db_session)

    marked = await repo.mark_match_stats_ok(fixtures["unplayed"].id)

    await db_session.refresh(fixtures["unplayed"])
    assert marked == 0
    assert fixtures["unplayed"].stats_ok is False


async def test_a_match_that_has_been_played_is_still_marked(db_session, fixtures) -> None:
    """The guard must not block the thing it is guarding."""
    repo = ScrapingRepository(db_session)

    marked = await repo.mark_match_stats_ok(fixtures["played"].id)

    await db_session.refresh(fixtures["played"])
    assert marked == 1
    assert fixtures["played"].stats_ok is True


async def test_a_nil_nil_draw_counts_as_played(db_session, fixtures) -> None:
    """0-0 is a result. Only NULL means "no score recorded"."""
    goalless = fixtures["unplayed"]
    goalless.home_score, goalless.away_score = 0, 0
    await db_session.flush()
    repo = ScrapingRepository(db_session)

    marked = await repo.mark_match_stats_ok(goalless.id)

    await db_session.refresh(goalless)
    assert marked == 1
    assert goalless.stats_ok is True
