"""import_teams_and_players must be idempotent (re-import must not crash).

Regression: create_team/create_player/create_match were plain INSERTs, so a
re-import (e.g. the admin "Re-importar equipos" button, or a retry after a
partial import) violated the (season_id, slug) unique constraint —
"llave duplicada ... players_season_id_slug_key". Now existing teams/players/
fixtures are skipped and only missing rows are added.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.features.scraping.client import ScrapingClient
from src.features.scraping.service import ScrapingService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.season import Season
from src.shared.models.team import Team

HOMEPAGE = """
<nav class="cabecera">
  <a class="team" alt="Alfa" href="/alfa"></a>
  <a class="team" alt="Beta" href="/beta"></a>
</nav>
"""

ROSTER = {
    "alfa": """
    <span class="nombre">Alfa</span>
    <a class="jugador" href="/jugadores/juan">Juan</a>
    <a class="jugador" href="/jugadores/pedro">Pedro</a>
    """,
    "beta": """
    <span class="nombre">Beta</span>
    <a class="jugador" href="/jugadores/luis">Luis</a>
    """,
}

CALENDAR = """
<section class="lista">
  <a class="partido" href="/partidos/5001-alfa-beta">
    <div class="fase">Jornada 1</div>
    <div class="equipo local"><img alt="Alfa"></div>
    <div class="equipo visitante"><img alt="Beta"></div>
    <div class="date">Sab 15/08 19:00h</div>
  </a>
</section>
"""


def _fake_fetch_factory():
    async def fake_fetch(self, url: str) -> str:
        if "/equipos/" in url and "/plantilla" in url:
            slug = url.split("/equipos/")[1].split("/plantilla")[0]
            return ROSTER.get(slug, "")
        if "/calendario/" in url:
            return CALENDAR
        return HOMEPAGE

    return fake_fetch


@pytest.mark.asyncio
async def test_reimport_is_idempotent(db_session, monkeypatch) -> None:
    monkeypatch.setattr(ScrapingClient, "fetch", _fake_fetch_factory())

    season = Season(name="2026-2027", matchday_start=1, kind="league")
    db_session.add(season)
    await db_session.flush()
    db_session.add(Matchday(season_id=season.id, number=1))
    await db_session.flush()

    svc = ScrapingService(db_session)

    first = await svc.import_teams_and_players(season.id, "laliga-26-27")
    assert first == {"teams": 2, "players": 3, "matches": 1}

    # Second run must NOT raise and must create nothing new.
    second = await svc.import_teams_and_players(season.id, "laliga-26-27")
    assert second == {"teams": 0, "players": 0, "matches": 0}

    # No duplicates in the DB.
    for model, expected in ((Team, 2), (Player, 3)):
        count = await db_session.scalar(
            select(func.count()).select_from(model).where(model.season_id == season.id)
        )
        assert count == expected
    match_count = await db_session.scalar(
        select(func.count())
        .select_from(Match)
        .join(Matchday, Match.matchday_id == Matchday.id)
        .where(Matchday.season_id == season.id)
    )
    assert match_count == 1
