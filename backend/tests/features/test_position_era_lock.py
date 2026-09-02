"""Player position is frozen by draft era (business rule).

Once the preseason draft is done the VPV position of a player is frozen —
even if futbolfantasy reclassifies him — until the winter draft, when it is
re-synced. So futbolfantasy-driven position CHANGES are allowed only in two
windows: pre-draft (before counting starts, ``current_md < matchday_start``)
and the winter re-sync (``current_md == matchday_winter``). Outside them a
change must be ignored; only EMPTY positions (new signings) may be filled.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.features.scraping.client import ScrapingClient
from src.features.scraping.photos import PhotoDownloader
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.season import Season
from src.shared.models.team import Team


def _pos_html(code: str) -> str:
    # parse_player_position reads span.position-box whose class carries the code.
    return f'<html><body><span class="position-box {code.lower()}">x</span></body></html>'


def _fake_fetch(code: str):
    html = _pos_html(code)

    async def fetch(self, url: str) -> str:
        return html

    return fetch


async def _seed(db_session, *, current_md: int, player_pos: str) -> tuple[Season, Player]:
    """Season with matchday_start=4, matchday_winter=20 and one played
    matchday numbered ``current_md`` (drives the season's current phase)."""
    season = Season(
        name="2026-2027", matchday_start=4, matchday_winter=20, kind="league"
    )
    db_session.add(season)
    await db_session.flush()
    a = Team(season_id=season.id, name="A", slug="a")
    b = Team(season_id=season.id, name="B", slug="b")
    db_session.add_all([a, b])
    await db_session.flush()
    player = Player(
        season_id=season.id, team_id=a.id, name="P", display_name="P",
        slug="p", position=player_pos,
    )
    md = Matchday(season_id=season.id, number=current_md, counts=True)
    db_session.add_all([player, md])
    await db_session.flush()
    db_session.add(
        Match(
            matchday_id=md.id, home_team_id=a.id, away_team_id=b.id,
            home_score=1, away_score=0, played_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()
    return season, player


@pytest.mark.asyncio
async def test_midseason_change_is_ignored(db_session, monkeypatch) -> None:
    """Between draft and winter, a source reclassification must NOT stick."""
    monkeypatch.setattr(ScrapingClient, "fetch", _fake_fetch("DEL"))
    season, player = await _seed(db_session, current_md=10, player_pos="MED")

    res = await PhotoDownloader(db_session).refresh_positions(season.id)
    await db_session.refresh(player)

    assert player.position == "MED"  # frozen — NOT changed to DEL
    assert res["positions_updated"] == 0


@pytest.mark.asyncio
async def test_predraft_change_is_applied(db_session, monkeypatch) -> None:
    """Before counting starts, positions still track futbolfantasy."""
    monkeypatch.setattr(ScrapingClient, "fetch", _fake_fetch("DEL"))
    season, player = await _seed(db_session, current_md=2, player_pos="MED")

    await PhotoDownloader(db_session).refresh_positions(season.id)
    await db_session.refresh(player)

    assert player.position == "DEL"


@pytest.mark.asyncio
async def test_winter_resync_change_is_applied(db_session, monkeypatch) -> None:
    """At the winter-draft matchday, positions are re-synced once."""
    monkeypatch.setattr(ScrapingClient, "fetch", _fake_fetch("DEL"))
    season, player = await _seed(db_session, current_md=20, player_pos="MED")

    await PhotoDownloader(db_session).refresh_positions(season.id)
    await db_session.refresh(player)

    assert player.position == "DEL"


@pytest.mark.asyncio
async def test_empty_position_is_always_filled(db_session, monkeypatch) -> None:
    """A new signing with no position gets one even mid-season (fill, not change)."""
    monkeypatch.setattr(ScrapingClient, "fetch", _fake_fetch("DEL"))
    season, player = await _seed(db_session, current_md=10, player_pos="")

    res = await PhotoDownloader(db_session).refresh_positions(season.id)
    await db_session.refresh(player)

    assert player.position == "DEL"
    assert res["positions_set"] == 1
