"""scrape_calendar must CREATE matches that appear after the initial import.

Regression for the Mundial 2026 round-of-32: knockout fixtures only get
published on the calendar once the group stage ends, so they were absent
from the initial import. scrape_calendar historically only *updated*
existing matches and skipped unknown source_ids, leaving the new matchday
with zero Match rows — the bracket showed provisional teams but the
squad/lineup view had no opponent to display.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.features.scraping.client import ScrapingClient
from src.features.scraping.service import ScrapingService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.season import Season
from src.shared.models.team import Team

# One match already in the DB (J3, source_id 1001) and one brand-new KO
# fixture (J4, source_id 2002) that must be created. Both future-dated and
# resultless so the "pending score" detail-page fallback stays inert.
CAL_HTML = """
<section class="lista">
  <a class="partido" href="/partidos/1001-alfa-beta">
    <div class="fase">Jornada 3</div>
    <div class="equipo local"><img alt="Alfa"></div>
    <div class="equipo visitante"><img alt="Beta"></div>
    <div class="date">Lun 29/06 20:00h</div>
  </a>
  <a class="partido" href="/partidos/2002-gamma-delta">
    <div class="fase">Jornada 4</div>
    <div class="equipo local"><img alt="Gamma"></div>
    <div class="equipo visitante"><img alt="Delta"></div>
    <div class="date">Mar 30/06 22:30h</div>
  </a>
</section>
"""


@pytest.mark.asyncio
async def test_scrape_calendar_creates_missing_knockout_match(
    db_session, monkeypatch
) -> None:
    async def fake_fetch(self, url: str) -> str:  # noqa: ANN001
        return CAL_HTML

    monkeypatch.setattr(ScrapingClient, "fetch", fake_fetch)

    season = Season(name="Mundial 2026", matchday_start=1, kind="tournament")
    db_session.add(season)
    await db_session.flush()

    teams = {}
    for name in ("Alfa", "Beta", "Gamma", "Delta"):
        t = Team(season_id=season.id, name=name, slug=name.lower())
        db_session.add(t)
        teams[name] = t
    j3 = Matchday(season_id=season.id, number=3)
    j4 = Matchday(season_id=season.id, number=4)
    db_session.add_all([j3, j4])
    await db_session.flush()

    # Existing J3 match — must be updated, never duplicated.
    existing = Match(
        matchday_id=j3.id,
        home_team_id=teams["Alfa"].id,
        away_team_id=teams["Beta"].id,
        source_id=1001,
    )
    db_session.add(existing)
    await db_session.flush()

    result = await ScrapingService(db_session).scrape_calendar(season.id)

    assert result["matches_created"] == 1

    # J4 now has the new match with the right teams.
    j4_matches = (
        await db_session.execute(select(Match).where(Match.matchday_id == j4.id))
    ).scalars().all()
    assert len(j4_matches) == 1
    created = j4_matches[0]
    assert created.source_id == 2002
    assert created.home_team_id == teams["Gamma"].id
    assert created.away_team_id == teams["Delta"].id
    assert created.played_at is not None

    # J3 was NOT duplicated.
    j3_matches = (
        await db_session.execute(select(Match).where(Match.matchday_id == j3.id))
    ).scalars().all()
    assert len(j3_matches) == 1

    # New matchday is now visible (first_match_at synced from the fixture).
    md4 = (
        await db_session.execute(
            select(Matchday).where(Matchday.id == j4.id)
        )
    ).scalar_one()
    assert md4.first_match_at is not None


@pytest.mark.asyncio
async def test_scrape_calendar_skips_when_team_unknown(db_session, monkeypatch) -> None:
    """A calendar match whose teams aren't in the season is skipped, not crashed."""

    async def fake_fetch(self, url: str) -> str:  # noqa: ANN001
        return CAL_HTML

    monkeypatch.setattr(ScrapingClient, "fetch", fake_fetch)

    season = Season(name="Mundial 2026", matchday_start=1, kind="tournament")
    db_session.add(season)
    await db_session.flush()
    # Only J3/J4 exist but NO teams named Gamma/Delta/Alfa/Beta.
    db_session.add_all(
        [Matchday(season_id=season.id, number=3), Matchday(season_id=season.id, number=4)]
    )
    await db_session.flush()

    result = await ScrapingService(db_session).scrape_calendar(season.id)
    assert result["matches_created"] == 0
