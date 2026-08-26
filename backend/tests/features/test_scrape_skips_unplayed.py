"""scrape_matchday must skip matchdays whose matches haven't been played.

Scraping an unplayed La Liga matchday would fetch player pages and match a
stray "jornada N" row from another competition (Copa/Segunda/loan), storing
phantom stats for a fixture that never happened. Only matches with a result
(home_score set) are processed.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.features.scraping.service import ScrapingService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


@pytest.mark.asyncio
async def test_scrape_matchday_skips_unplayed(db_session) -> None:
    season = Season(name="2026-2027", matchday_start=4, matchday_current=1, kind="league")
    db_session.add(season)
    await db_session.flush()
    home = Team(season_id=season.id, name="A", slug="a")
    away = Team(season_id=season.id, name="B", slug="b")
    db_session.add_all([home, away])
    await db_session.flush()
    md = Matchday(season_id=season.id, number=4, counts=True, status="pending")
    db_session.add(md)
    await db_session.flush()
    # Unplayed match: no result yet (home_score is None).
    db_session.add(
        Match(
            matchday_id=md.id,
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=None,
            away_score=None,
            counts=True,
        )
    )
    await db_session.flush()

    result = await ScrapingService(db_session).scrape_matchday(season.id, 4)

    assert result == {"processed": 0, "skipped": 0, "errors": 0}
    count = await db_session.scalar(select(func.count()).select_from(PlayerStat))
    assert count == 0
