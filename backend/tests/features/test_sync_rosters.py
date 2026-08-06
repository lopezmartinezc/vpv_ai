"""sync_rosters reconciles rosters with the live source, transfers included.

A player who moves clubs appears in a different team's roster. The old
per-team logic would have tried to create_player (crash on the (season,slug)
unique constraint) and never updated the team; now it MOVES the player and
soft-deactivates only players gone from every scraped squad.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.features.scraping.client import ScrapingClient
from src.features.scraping.service import ScrapingService
from src.shared.models.player import Player
from src.shared.models.season import Season
from src.shared.models.team import Team


def _roster(*names: str) -> str:
    rows = "".join(f'<a class="jugador" href="/jugadores/{n}">{n}</a>' for n in names)
    return f'<span class="nombre">T</span>{rows}'


def _fake_fetch():
    # team A keeps "stayer"; "mover" left, "cut" dropped.
    # team B now has "mover" (transfer) and "newbie" (new signing).
    rosters = {"a": _roster("stayer"), "b": _roster("mover", "newbie")}

    async def fetch(self, url: str) -> str:
        slug = url.split("/equipos/")[1].split("/plantilla")[0]
        return rosters[slug]

    return fetch


@pytest.mark.asyncio
async def test_sync_rosters_handles_transfer_add_and_cut(db_session, monkeypatch) -> None:
    monkeypatch.setattr(ScrapingClient, "fetch", _fake_fetch())

    season = Season(name="2026-2027", matchday_start=1, kind="league")
    db_session.add(season)
    await db_session.flush()
    a = Team(season_id=season.id, name="A", slug="a")
    b = Team(season_id=season.id, name="B", slug="b")
    db_session.add_all([a, b])
    await db_session.flush()

    def mk(slug, team, avail=True):
        p = Player(
            season_id=season.id,
            team_id=team.id,
            name=slug,
            display_name=slug,
            slug=slug,
            position="MED",
            is_available=avail,
        )
        db_session.add(p)
        return p

    mk("stayer", a)
    mk("mover", a)  # will transfer to B
    mk("cut", a)  # dropped from all rosters
    await db_session.flush()

    result = await ScrapingService(db_session).sync_rosters(season.id)

    assert result["players_added"] == 1  # newbie
    assert result["players_moved"] == 1  # mover a -> b
    assert result["players_deactivated"] == 1  # cut

    by_slug = {
        p.slug: p
        for p in (
            await db_session.execute(select(Player).where(Player.season_id == season.id))
        ).scalars()
    }
    # Transfer applied on the CURRENT team only.
    assert by_slug["mover"].team_id == b.id
    assert by_slug["mover"].is_available is True
    # New signing created on its team.
    assert by_slug["newbie"].team_id == b.id
    # Cut player soft-deactivated (still in DB).
    assert by_slug["cut"].is_available is False
    # Stayer untouched.
    assert by_slug["stayer"].team_id == a.id and by_slug["stayer"].is_available is True
