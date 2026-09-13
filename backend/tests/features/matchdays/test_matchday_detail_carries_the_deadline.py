"""The matchday detail carries the effective lineup deadline.

The home answered "has the deadline passed?" twice. The part that follows your
matchday asked the personal deadline status, so visitors never got an answer;
the rest of the page took the first kick-off minus the margin. With an early J6
match (13/09/2026) the second one decided J6 had started while its lineups were
still open. One answer, from the server, for everyone: the same
`effective_deadline` the lineup rules use, override included.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.matchday import Matchday
from src.shared.models.season import Season

EARLY_MATCH = datetime(2026, 9, 13, 18, 30, tzinfo=UTC)
OVERRIDE = datetime(2026, 9, 15, 17, 0, tzinfo=UTC)


@pytest.fixture
async def season(db_session: AsyncSession) -> Season:
    season = Season(
        name="2026-2027",
        status="active",
        matchday_start=6,
        matchday_current=6,
        matchday_end=38,
        lineup_deadline_min=30,
    )
    db_session.add(season)
    await db_session.flush()
    return season


async def detail(
    client: AsyncClient,
    db: AsyncSession,
    season: Season,
    *,
    first_match_at: datetime | None,
    deadline_at: datetime | None,
) -> str | None:
    db.add(
        Matchday(
            season_id=season.id,
            number=6,
            status="in_progress",
            stats_ok=False,
            first_match_at=first_match_at,
            deadline_at=deadline_at,
        )
    )
    await db.flush()
    response = await client.get(f"/api/matchdays/{season.id}/6")
    assert response.status_code == 200
    return response.json()["deadline_at"]


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def test_an_override_is_the_deadline_even_after_an_early_match(
    client: AsyncClient, db_session: AsyncSession, season: Season
) -> None:
    value = await detail(
        client, db_session, season, first_match_at=EARLY_MATCH, deadline_at=OVERRIDE
    )
    assert value is not None and parse(value) == OVERRIDE


async def test_without_an_override_it_is_the_kick_off_minus_the_margin(
    client: AsyncClient, db_session: AsyncSession, season: Season
) -> None:
    value = await detail(client, db_session, season, first_match_at=EARLY_MATCH, deadline_at=None)
    assert value is not None
    assert parse(value) == datetime(2026, 9, 13, 18, 0, tzinfo=UTC)


async def test_no_information_means_no_deadline(
    client: AsyncClient, db_session: AsyncSession, season: Season
) -> None:
    assert await detail(client, db_session, season, first_match_at=None, deadline_at=None) is None
