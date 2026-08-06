"""Admin scrape-status: what has been imported for a season + last result.

Backs the admin season-config panel that shows which parts (teams, squads,
calendar, photos) have been scraped and with what result.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.features.seasons.service import SeasonService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.scraping_log import ScrapingLog
from src.shared.models.season import Season
from src.shared.models.team import Team


@pytest.mark.asyncio
async def test_scrape_status_reports_counts_and_last_import(db_session) -> None:
    season = Season(name="2026-2027", matchday_start=1, matchday_current=0, kind="league")
    db_session.add(season)
    await db_session.flush()

    t1 = Team(season_id=season.id, name="Alavés", slug="alaves")
    t2 = Team(season_id=season.id, name="Getafe", slug="getafe")
    db_session.add_all([t1, t2])
    await db_session.flush()

    # 3 players: one fully scraped (position + photo), one with position only,
    # one bare (no position, no photo).
    db_session.add_all(
        [
            Player(
                season_id=season.id, team_id=t1.id, name="A", display_name="A",
                slug="a", position="DEL", photo_path="/x/a.webp",
            ),
            Player(
                season_id=season.id, team_id=t1.id, name="B", display_name="B",
                slug="b", position="MED", photo_path=None,
            ),
            Player(
                season_id=season.id, team_id=t2.id, name="C", display_name="C",
                slug="c", position="", photo_path=None,
            ),
        ]
    )
    # 2 matchdays: J1 has fixtures (first_match_at set), J2 doesn't.
    j1 = Matchday(
        season_id=season.id, number=1, counts=True,
        first_match_at=datetime(2026, 8, 15, 19, tzinfo=UTC),
    )
    j2 = Matchday(season_id=season.id, number=2, counts=True)
    db_session.add_all([j1, j2])
    await db_session.flush()

    # 2 matches in J1: one played (score), one scheduled (no score).
    db_session.add_all(
        [
            Match(
                matchday_id=j1.id, home_team_id=t1.id, away_team_id=t2.id,
                home_score=2, away_score=1,
                played_at=datetime(2026, 8, 15, 19, tzinfo=UTC),
            ),
            Match(
                matchday_id=j1.id, home_team_id=t2.id, away_team_id=t1.id,
                played_at=datetime(2026, 8, 16, 21, tzinfo=UTC),
            ),
        ]
    )
    db_session.add(
        ScrapingLog(
            season_id=season.id,
            job_type="import_setup",
            status="ok",
            message="2 equipos, 3 jugadores, 2 partidos",
            detail={"teams": 2, "players": 3, "matches": 2},
        )
    )
    await db_session.flush()

    status = await SeasonService(db_session).get_scrape_status(season.id)

    assert status.teams == 2
    assert status.players_total == 3
    assert status.players_with_position == 2
    assert status.players_with_photo == 1
    assert status.matchdays_total == 2
    assert status.matchdays_counting == 2
    assert status.matchdays_with_fixtures == 1
    assert status.matches_total == 2
    assert status.matches_with_result == 1
    assert status.first_match_at is not None
    assert status.last_match_at is not None

    assert status.last_import_status == "ok"
    assert status.last_import_detail == {"teams": 2, "players": 3, "matches": 2}
    assert status.last_import_at is not None


@pytest.mark.asyncio
async def test_scrape_status_empty_season(db_session) -> None:
    season = Season(name="2027-2028", matchday_start=1, matchday_current=0, kind="league")
    db_session.add(season)
    await db_session.flush()

    status = await SeasonService(db_session).get_scrape_status(season.id)

    assert status.teams == 0
    assert status.players_total == 0
    assert status.matches_total == 0
    assert status.last_import_status is None
    assert status.last_import_at is None
