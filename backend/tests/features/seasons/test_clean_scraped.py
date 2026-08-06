"""Admin clean of scraped data — reset a season setup safely.

Lets the admin wipe teams/players/calendar to re-import cleanly. Guarded:
only on a 'setup' season with no game data (player_stats/lineups/drafts).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.core.exceptions import BusinessRuleError
from src.features.seasons.service import SeasonService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


async def _seed(db, status: str = "setup"):
    season = Season(name="2026-2027", matchday_start=1, kind="league", status=status)
    db.add(season)
    await db.flush()
    t1 = Team(season_id=season.id, name="Alfa", slug="alfa")
    t2 = Team(season_id=season.id, name="Beta", slug="beta")
    db.add_all([t1, t2])
    await db.flush()
    db.add_all(
        [
            Player(
                season_id=season.id,
                team_id=t1.id,
                name="J",
                display_name="J",
                slug="j",
                position="MED",
            ),
            Player(
                season_id=season.id,
                team_id=t2.id,
                name="K",
                display_name="K",
                slug="k",
                position="DEL",
            ),
        ]
    )
    md = Matchday(season_id=season.id, number=1)
    db.add(md)
    await db.flush()
    db.add(Match(matchday_id=md.id, home_team_id=t1.id, away_team_id=t2.id, source_id=1))
    await db.flush()
    return season, md, t1


@pytest.mark.asyncio
async def test_clean_all_wipes_everything(db_session) -> None:
    season, _md, _t = await _seed(db_session)
    svc = SeasonService(db_session)

    deleted = await svc.clean_scraped(season.id, "all")

    assert deleted == {"matches": 1, "players": 2, "teams": 2}
    counts = await svc.repo.get_scrape_status_counts(season.id)
    assert counts["teams"] == 0
    assert counts["players_total"] == 0
    assert counts["matches_total"] == 0


@pytest.mark.asyncio
async def test_clean_calendar_only(db_session) -> None:
    season, _md, _t = await _seed(db_session)
    svc = SeasonService(db_session)

    deleted = await svc.clean_scraped(season.id, "calendar")

    assert deleted["matches"] == 1
    counts = await svc.repo.get_scrape_status_counts(season.id)
    assert counts["matches_total"] == 0
    assert counts["players_total"] == 2  # untouched
    assert counts["teams"] == 2


@pytest.mark.asyncio
async def test_clean_teams_requires_players_and_matches_gone(db_session) -> None:
    season, _md, _t = await _seed(db_session)
    svc = SeasonService(db_session)

    with pytest.raises(BusinessRuleError):
        await svc.clean_scraped(season.id, "teams")

    # After clearing calendar + rosters, teams can go.
    await svc.clean_scraped(season.id, "calendar")
    await svc.clean_scraped(season.id, "rosters")
    deleted = await svc.clean_scraped(season.id, "teams")
    assert deleted["teams"] == 2


@pytest.mark.asyncio
async def test_clean_refused_when_not_setup(db_session) -> None:
    season, _md, _t = await _seed(db_session, status="active")
    with pytest.raises(BusinessRuleError):
        await SeasonService(db_session).clean_scraped(season.id, "all")


@pytest.mark.asyncio
async def test_clean_refused_when_game_data_exists(db_session) -> None:
    season, md, _t1 = await _seed(db_session)
    player = (
        (await db_session.execute(select(Player).where(Player.season_id == season.id)))
        .scalars()
        .first()
    )
    db_session.add(PlayerStat(player_id=player.id, matchday_id=md.id, position="MED", pts_total=5))
    await db_session.flush()

    with pytest.raises(BusinessRuleError):
        await SeasonService(db_session).clean_scraped(season.id, "all")
