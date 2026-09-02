"""La Liga scraping via the match-page path — history-safe team attribution.

Two goals:

1. Characterisation: the La Liga match page (Vue 2026 redesign) parses with
   the same ``parse_match_page_players`` used for tournaments — teams split,
   slugs, and the full event set (goals, penalties, assists, yellow/red).
   Guards against the source changing under us again.

2. History-safety (RED until the redesign lands): a player who has since
   moved to another club must still be attributed to the team he actually
   lined up for THAT matchday, resolved by ``slug`` across the whole season
   (not restricted to the current roster of the parsed team).

Fixture: a real J-early Celta 1–2 Osasuna, trimmed to the two per-team
``tablestats`` tables + score block.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from src.features.scraping.client import ScrapingClient
from src.features.scraping.parsers import parse_match_page_players
from src.features.scraping.service import ScrapingService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team

FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "scraping"
    / "match_laliga_celta_osasuna.html"
)


def _html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Parser characterisation
# ---------------------------------------------------------------------------


def test_parses_laliga_match_page_teams_and_events() -> None:
    players = parse_match_page_players(
        _html(),
        matchday_number=1,
        home_team_name="Celta",
        away_team_name="Osasuna",
    )
    assert len(players) == 48
    assert sum(1 for p in players if p.team_name == "Celta") == 24
    assert sum(1 for p in players if p.team_name == "Osasuna") == 24
    # slug is the join key with players.slug — must be 100% present.
    assert all(p.slug for p in players)

    by_slug = {p.slug: p for p in players}
    # Goals / penalties / assists / cards must survive the switch of source.
    assert by_slug["iago-aspas"].stats.goals == 1
    assert by_slug["ante-budimir"].stats.penalty_goals == 1
    assert by_slug["miguel-roman"].stats.assists == 1
    assert by_slug["marcos-alonso"].stats.red_card is True
    assert by_slug["jonathan-dubasin"].stats.yellow_card is True


# ---------------------------------------------------------------------------
# 2. History-safe team attribution via the service (RED)
# ---------------------------------------------------------------------------


def _fake_fetch():
    html = _html()

    async def fetch(self, url: str) -> str:  # noqa: ANN001
        return html

    return fetch


@pytest.mark.asyncio
async def test_scrape_attributes_moved_player_to_historical_team(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(ScrapingClient, "fetch", _fake_fetch())

    # Season configured to use the match-page path (the target for La Liga).
    season = Season(
        name="2026-2027",
        matchday_start=1,
        kind="league",
        tournament_config={"stats_source": "match_page"},
    )
    db_session.add(season)
    await db_session.flush()

    celta = Team(season_id=season.id, name="Celta", slug="celta")
    osasuna = Team(season_id=season.id, name="Osasuna", slug="osasuna")
    other = Team(season_id=season.id, name="Other", slug="other")
    db_session.add_all([celta, osasuna, other])
    await db_session.flush()

    # Iago Aspas played this matchday for Celta but has SINCE moved to
    # "Other" — so his current roster team is Other, not Celta.
    aspas = Player(
        season_id=season.id,
        team_id=other.id,
        name="Iago Aspas",
        display_name="Iago Aspas",
        slug="iago-aspas",
        position="DEL",
    )
    db_session.add(aspas)

    md = Matchday(season_id=season.id, number=1, counts=True)
    db_session.add(md)
    await db_session.flush()

    match = Match(
        matchday_id=md.id,
        home_team_id=celta.id,
        away_team_id=osasuna.id,
        home_score=1,
        away_score=2,
        source_url="https://www.futbolfantasy.com/partidos/22423-celta-osasuna",
        played_at=datetime(2026, 8, 15, tzinfo=UTC),
    )
    db_session.add(match)
    await db_session.flush()

    await ScrapingService(db_session).scrape_matchday(season.id, 1)
    await db_session.flush()

    row = (
        await db_session.execute(
            select(PlayerStat).where(PlayerStat.player_id == aspas.id)
        )
    ).scalar_one_or_none()

    # He must NOT be dropped just because his CURRENT club isn't Celta, and
    # the matchday must be pinned to the team he actually played for: Celta.
    assert row is not None, "moved player was skipped (roster-restricted lookup)"
    assert row.team_id == celta.id
