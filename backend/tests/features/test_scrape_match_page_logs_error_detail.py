"""The panel log of a single-match scrape says WHY it failed.

On 2026-10-22 the postponed Levante - Athletic (J6) failed to scrape because
the server could not reach futbolfantasy for ten minutes (ConnectTimeout). The
panel only showed "Fin [match_page]: procesados=0, errores=1"; the cause was
returned in ``error_details`` and written to the journal, never to the
scraping log the panel reads.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.log_repository import ScrapingLogRepository
from src.features.scraping.service import ScrapingService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.season import Season
from src.shared.models.team import Team

SOURCE_URL = "https://www.futbolfantasy.com/partidos/22478-levante-athletic"


@pytest.mark.asyncio
async def test_fin_log_carries_the_fetch_error(db_session, monkeypatch) -> None:
    async def fetch(self, url: str) -> str:
        raise ScrapingError(url, httpx.ConnectTimeout(""))

    written: list[dict] = []

    async def write_log(log: dict) -> None:
        written.append(log)

    monkeypatch.setattr(ScrapingClient, "fetch", fetch)
    monkeypatch.setattr(ScrapingLogRepository, "write_log", staticmethod(write_log))

    season = Season(
        name="2026-2027",
        matchday_start=1,
        kind="league",
        tournament_config={"stats_source": "match_page"},
    )
    db_session.add(season)
    await db_session.flush()

    levante = Team(season_id=season.id, name="Levante", slug="levante")
    athletic = Team(season_id=season.id, name="Athletic", slug="athletic")
    db_session.add_all([levante, athletic])
    md = Matchday(season_id=season.id, number=6, counts=True)
    db_session.add(md)
    await db_session.flush()

    match = Match(
        matchday_id=md.id,
        home_team_id=levante.id,
        away_team_id=athletic.id,
        home_score=3,
        away_score=1,
        source_url=SOURCE_URL,
        played_at=datetime(2026, 10, 21, 18, 0, tzinfo=UTC),
    )
    db_session.add(match)
    await db_session.flush()

    summary = await ScrapingService(db_session).scrape_match_players(season.id, 6, match.id)

    assert summary["errors"] == 1
    fin = next(log for log in written if log["message"].startswith("Fin [match_page]"))
    assert fin["status"] == "warning"
    assert "ConnectTimeout" in fin["message"]
