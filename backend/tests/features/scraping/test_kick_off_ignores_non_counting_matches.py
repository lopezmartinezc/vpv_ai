"""A jornada's first kick-off comes from the matches that count.

J6 of 2026-27 had one match played on 3 September and marked as not counting.
``first_match_at`` took the earliest match of the jornada, so the lineup
deadline (kick-off minus the margin) fell on 3/09: nobody could field a side
for a jornada that really started on the 15th, and the scheduler rolled the
current matchday forward as if J6 had begun. A match that does not count must
not decide when a jornada starts. If none counts, the earliest of all is kept.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.scraping.repository import ScrapingRepository
from src.shared.models.matchday import Match, Matchday
from src.shared.models.season import Season
from src.shared.models.team import Team

EARLY = datetime(2026, 9, 3, 19, 0, tzinfo=UTC)
FIRST_COUNTING = datetime(2026, 9, 15, 17, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 16, 17, 0, tzinfo=UTC)
PAIRS = [(0, 1), (2, 3), (0, 2)]


@pytest.fixture
async def league(db_session: AsyncSession) -> tuple[Season, list[Team]]:
    season = Season(name="2026-2027", status="active", matchday_start=6, matchday_end=38)
    db_session.add(season)
    await db_session.flush()
    teams = [Team(season_id=season.id, name=n, slug=n.lower()) for n in ("A", "B", "C", "D")]
    db_session.add_all(teams)
    await db_session.flush()
    return season, teams


async def kick_off(
    db: AsyncSession, league: tuple[Season, list[Team]], fixtures: list[tuple[datetime, bool]]
) -> datetime | None:
    """Create J6 with these (played_at, counts) fixtures, sync, read first_match_at."""
    season, teams = league
    jornada = Matchday(season_id=season.id, number=6, counts=True)
    db.add(jornada)
    await db.flush()
    for (home, away), (played_at, counts) in zip(PAIRS, fixtures, strict=False):
        db.add(
            Match(
                matchday_id=jornada.id,
                home_team_id=teams[home].id,
                away_team_id=teams[away].id,
                played_at=played_at,
                counts=counts,
            )
        )
    await db.flush()
    await ScrapingRepository(db).sync_matchday_first_match_at(season.id)
    result = await db.execute(select(Matchday.first_match_at).where(Matchday.id == jornada.id))
    return result.scalar_one()


async def test_an_early_match_that_does_not_count_does_not_start_the_jornada(
    db_session: AsyncSession, league: tuple[Season, list[Team]]
) -> None:
    fixtures = [(EARLY, False), (FIRST_COUNTING, True), (LATER, True)]
    assert await kick_off(db_session, league, fixtures) == FIRST_COUNTING


async def test_a_counting_match_played_first_still_starts_it(
    db_session: AsyncSession, league: tuple[Season, list[Team]]
) -> None:
    fixtures = [(EARLY, True), (FIRST_COUNTING, False)]
    assert await kick_off(db_session, league, fixtures) == EARLY


async def test_a_jornada_where_nothing_counts_keeps_its_earliest_match(
    db_session: AsyncSession, league: tuple[Season, list[Team]]
) -> None:
    fixtures = [(EARLY, False), (LATER, False)]
    assert await kick_off(db_session, league, fixtures) == EARLY
