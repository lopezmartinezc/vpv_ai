"""player_stats.team_id pins the team a player played for each matchday.

players.team_id is the CURRENT team; a mid-season transfer updates it. Past
matchdays must not be relabelled — historical home/away derivation now reads
player_stats.team_id (set at scrape time, never overwritten on re-scrape),
falling back to the current team only for un-backfilled rows.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from src.features.scraping.parsers import PlayerMatchdayStats
from src.features.scraping.repository import ScrapingRepository
from src.features.scraping.scoring import PointsBreakdown
from src.features.stats.repository_advanced import AdvancedStatsRepository
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


def _stats() -> PlayerMatchdayStats:
    return PlayerMatchdayStats(
        matchday_number=1, played=True, home_score=1, away_score=0, result=2,
        goals_for=1, goals_against=0, event=None, event_minute=None, minutes_played=90,
        goals=0, penalty_goals=0, assists=0, penalties_saved=0, woodwork=0,
        penalties_won=0, penalties_missed=0, own_goals=0, yellow_card=False,
        yellow_removed=False, double_yellow=False, red_card=False,
        penalties_committed=0, marca_rating=None, as_picas=None,
    )


def _breakdown() -> PointsBreakdown:
    return PointsBreakdown(**{f: 0 for f in PointsBreakdown.__dataclass_fields__})


@pytest.mark.asyncio
async def test_upsert_pins_team_id_and_never_overwrites(db_session) -> None:
    season = Season(name="2026-2027", matchday_start=1, kind="league")
    db_session.add(season)
    await db_session.flush()
    a = Team(season_id=season.id, name="A", slug="a")
    b = Team(season_id=season.id, name="B", slug="b")
    db_session.add_all([a, b])
    await db_session.flush()
    p = Player(season_id=season.id, team_id=a.id, name="P", display_name="P", slug="p", position="DEL")
    md = Matchday(season_id=season.id, number=1)
    db_session.add_all([p, md])
    await db_session.flush()

    repo = ScrapingRepository(db_session)
    # First scrape: player on team A.
    await repo.upsert_player_stat(
        player_id=p.id, matchday_id=md.id, match_id=None, position="DEL",
        stats=_stats(), breakdown=_breakdown(), team_id=a.id,
    )
    await db_session.flush()
    row = (await db_session.execute(select(PlayerStat))).scalar_one()
    assert row.team_id == a.id

    # Re-scrape AFTER a transfer (current team now B): must NOT overwrite the
    # team the player actually played for that matchday.
    await repo.upsert_player_stat(
        player_id=p.id, matchday_id=md.id, match_id=None, position="DEL",
        stats=_stats(), breakdown=_breakdown(), team_id=b.id,
    )
    await db_session.flush()
    row = (await db_session.execute(select(PlayerStat))).scalar_one()
    assert row.team_id == a.id  # still A, not B


@pytest.mark.asyncio
async def test_splits_use_per_matchday_team_not_current(db_session) -> None:
    season = Season(name="2026-2027", matchday_start=1, kind="league")
    db_session.add(season)
    await db_session.flush()
    a = Team(season_id=season.id, name="A", slug="a")
    c = Team(season_id=season.id, name="C", slug="c")
    b = Team(season_id=season.id, name="B", slug="b")
    db_session.add_all([a, c, b])
    await db_session.flush()

    # Player CURRENTLY on team B (transferred), but played for A earlier.
    p = Player(season_id=season.id, team_id=b.id, name="P", display_name="P", slug="p", position="DEL")
    md1 = Matchday(season_id=season.id, number=1, counts=True)
    md2 = Matchday(season_id=season.id, number=2, counts=True)
    db_session.add_all([p, md1, md2])
    await db_session.flush()

    # md1: A home vs C  -> A is home. md2: C home vs A -> A is away.
    m1 = Match(matchday_id=md1.id, home_team_id=a.id, away_team_id=c.id,
               home_score=1, away_score=0, played_at=datetime(2026, 8, 15, tzinfo=UTC))
    m2 = Match(matchday_id=md2.id, home_team_id=c.id, away_team_id=a.id,
               home_score=0, away_score=1, played_at=datetime(2026, 8, 22, tzinfo=UTC))
    db_session.add_all([m1, m2])
    await db_session.flush()

    # player_stats pin team_id = A for both (the team he played for then).
    db_session.add_all([
        PlayerStat(player_id=p.id, matchday_id=md1.id, match_id=m1.id, team_id=a.id,
                   position="DEL", played=True, pts_total=8),
        PlayerStat(player_id=p.id, matchday_id=md2.id, match_id=m2.id, team_id=a.id,
                   position="DEL", played=True, pts_total=4),
    ])
    await db_session.flush()

    splits = await AdvancedStatsRepository(db_session).get_player_splits(season.id, p.id)
    by_loc = {s.location: s.matches for s in splits}
    # A was home in md1 and away in md2 -> 1 home + 1 away, despite current team B.
    assert by_loc.get("home") == 1
    assert by_loc.get("away") == 1
