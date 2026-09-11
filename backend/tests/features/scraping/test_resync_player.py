"""Re-sync one player's stats, and re-pin the team he actually played for.

player_stats.team_id is deliberately pinned to the first scrape: a real
mid-season transfer must not rewrite the club a player turned out for in
past matchdays. But when the pin captured a mistake — a loan signed up
under the parent club, so every row says Villarreal for matches played at
Levante — nothing can correct it. A re-scrape preserves the wrong value by
design, which is the pin doing its job on bad input.

So the override is explicit and per player: an admin who has just fixed the
roster team says "and re-pin his rows too". It is never automatic, because
automatic is exactly what the pin exists to prevent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from src.features.scraping.parsers import PlayerMatchdayStats
from src.features.scraping.service import ScrapingService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


def _row(matchday_number: int, *, result: int = 2, goals_against: int = 0) -> PlayerMatchdayStats:
    """One row of his own stats table on futbolfantasy — where the result and
    goals conceded come from, which is why his POINTS were right all along."""
    return PlayerMatchdayStats(
        matchday_number=matchday_number,
        played=True,
        home_score=2,
        away_score=goals_against,
        result=result,
        goals_for=2,
        goals_against=goals_against,
        event=None,
        event_minute=None,
        minutes_played=90,
        goals=1,
        penalty_goals=0,
        assists=0,
        penalties_saved=0,
        woodwork=0,
        penalties_won=0,
        penalties_missed=0,
        own_goals=0,
        yellow_card=False,
        yellow_removed=False,
        double_yellow=False,
        red_card=False,
        penalties_committed=0,
        marca_rating=None,
        as_picas=None,
    )


@pytest.fixture
async def scene(db_session):
    """A loan signed up under the wrong club: his rows say Villarreal."""
    season = Season(
        name="2026-2027", matchday_start=6, matchday_current=5, matchday_end=38, kind="league"
    )
    db_session.add(season)
    await db_session.flush()
    parent = Team(season_id=season.id, name="Villarreal", slug="villarreal")
    actual = Team(season_id=season.id, name="Levante", slug="levante")
    rival = Team(season_id=season.id, name="Rival", slug="rival")
    db_session.add_all([parent, actual, rival])
    await db_session.flush()
    md = Matchday(season_id=season.id, number=1, counts=False)
    db_session.add(md)
    await db_session.flush()
    # Both clubs played that matchday, each in their own match.
    parent_match = Match(matchday_id=md.id, home_team_id=parent.id, away_team_id=rival.id)
    actual_match = Match(matchday_id=md.id, home_team_id=actual.id, away_team_id=rival.id)
    db_session.add_all([parent_match, actual_match])
    await db_session.flush()
    # The roster has already been corrected to Levante by the admin.
    player = Player(
        season_id=season.id,
        team_id=actual.id,
        name="Thiago",
        display_name="Thiago",
        slug="thiago-fernandez",
        position="MED",
    )
    db_session.add(player)
    await db_session.flush()
    # ...but his existing row still carries the parent club and its match.
    db_session.add(
        PlayerStat(
            player_id=player.id,
            matchday_id=md.id,
            match_id=parent_match.id,
            team_id=parent.id,
            position="MED",
            played=True,
            minutes_played=90,
            pts_total=5,
        )
    )
    await db_session.flush()
    return {
        "season": season,
        "player": player,
        "md": md,
        "parent": parent,
        "actual": actual,
        "actual_match": actual_match,
        "parent_match": parent_match,
    }


async def _resync(db_session, scene, **kwargs):
    service = ScrapingService(db_session)
    with (
        patch("src.features.scraping.service.ScrapingClient") as client,
        patch("src.features.scraping.service.parse_player_all_matchdays", return_value=[_row(1)]),
    ):
        client.return_value.__aenter__.return_value.fetch = AsyncMock(return_value="<html/>")
        return await service.resync_player(scene["season"].id, scene["player"].id, **kwargs)


async def _stat(db_session, scene) -> PlayerStat:
    row = await db_session.scalar(
        select(PlayerStat).where(
            PlayerStat.player_id == scene["player"].id,
            PlayerStat.matchday_id == scene["md"].id,
        )
    )
    assert row is not None
    await db_session.refresh(row)
    return row


@pytest.mark.asyncio
async def test_repin_moves_the_row_to_the_club_he_played_for(db_session, scene) -> None:
    await _resync(db_session, scene, repin=True)
    row = await _stat(db_session, scene)
    assert row.team_id == scene["actual"].id
    assert row.match_id == scene["actual_match"].id


@pytest.mark.asyncio
async def test_without_repin_the_pin_still_protects_a_real_transfer(db_session, scene) -> None:
    """The default must stay the safe one: a player who genuinely moved keeps
    the club he turned out for in past matchdays."""
    await _resync(db_session, scene, repin=False)
    row = await _stat(db_session, scene)
    assert row.team_id == scene["parent"].id
    assert row.match_id == scene["parent_match"].id


@pytest.mark.asyncio
async def test_points_are_recomputed_from_his_own_page(db_session, scene) -> None:
    result = await _resync(db_session, scene, repin=True)
    row = await _stat(db_session, scene)
    assert result["rows_updated"] == 1
    assert row.pts_total != 5  # recomputed, not left at the seeded value
    assert row.goals == 1 and row.minutes_played == 90


@pytest.mark.asyncio
async def test_it_touches_only_the_player_asked_for(db_session, scene) -> None:
    other = Player(
        season_id=scene["season"].id,
        team_id=scene["parent"].id,
        name="Otro",
        display_name="Otro",
        slug="otro",
        position="DEF",
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        PlayerStat(
            player_id=other.id,
            matchday_id=scene["md"].id,
            team_id=scene["parent"].id,
            position="DEF",
            played=True,
            minutes_played=90,
            pts_total=7,
        )
    )
    await db_session.flush()
    await _resync(db_session, scene, repin=True)
    untouched = await db_session.scalar(select(PlayerStat).where(PlayerStat.player_id == other.id))
    await db_session.refresh(untouched)
    assert untouched.team_id == scene["parent"].id
    assert untouched.pts_total == 7


@pytest.mark.asyncio
async def test_a_matchday_range_limits_what_is_touched(db_session, scene) -> None:
    result = await _resync(db_session, scene, repin=True, start=5, end=10)
    assert result["rows_updated"] == 0
    row = await _stat(db_session, scene)
    assert row.team_id == scene["parent"].id
