"""Pre-draft matchdays (counts=false) are hidden by default but can be shown.

Matchdays before ``matchday_start`` are ``counts=false`` (league view excludes
them). While preparing the draft the admin wants to preview this season's raw
output, so ``get_player_stats(include_noncounting=True)`` includes them.
"""

from __future__ import annotations

import pytest

from src.features.stats.repository import StatsRepository
from src.shared.models.matchday import Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


@pytest.mark.asyncio
async def test_get_player_stats_predraft_toggle(db_session) -> None:
    season = Season(name="2026-2027", matchday_start=4, kind="league")
    db_session.add(season)
    await db_session.flush()

    team = Team(season_id=season.id, name="A", slug="a")
    db_session.add(team)
    await db_session.flush()

    player = Player(
        season_id=season.id,
        team_id=team.id,
        name="P",
        display_name="P",
        slug="p",
        position="DEL",
    )
    md_pre = Matchday(season_id=season.id, number=1, counts=False)  # pre-draft
    md_league = Matchday(season_id=season.id, number=4, counts=True)  # counts
    db_session.add_all([player, md_pre, md_league])
    await db_session.flush()

    db_session.add_all(
        [
            PlayerStat(
                player_id=player.id,
                matchday_id=md_pre.id,
                position="DEL",
                played=True,
                minutes_played=90,
                pts_total=7,
                pts_starter=1,
            ),
            PlayerStat(
                player_id=player.id,
                matchday_id=md_league.id,
                position="DEL",
                played=True,
                minutes_played=90,
                pts_total=5,
                pts_starter=1,
            ),
        ]
    )
    await db_session.flush()

    repo = StatsRepository(db_session)

    # Default: only the counting matchday (J4) → 5 pts, 1 matchday.
    default = await repo.get_player_stats(season.id)
    assert len(default) == 1
    assert default[0].total_points == 5
    assert default[0].matchdays_played == 1

    # With the toggle: pre-draft J1 included too → 7 + 5 = 12 pts, 2 matchdays.
    both = await repo.get_player_stats(season.id, include_noncounting=True)
    assert len(both) == 1
    assert both[0].total_points == 12
    assert both[0].matchdays_played == 2
