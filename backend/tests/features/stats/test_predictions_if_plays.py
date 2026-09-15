"""The forecast tells apart what a player scores if he plays from how often he
starts, so a better source of the second can replace it without counting it
twice."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.stats.service_advanced import AdvancedStatsService
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team


async def test_xpts_is_the_if_plays_forecast_discounted_by_starts(
    db_session: AsyncSession,
) -> None:
    db = db_session
    season = Season(name="2026-2027", status="active", matchday_start=1, matchday_end=38)
    db.add(season)
    await db.flush()
    home = Team(season_id=season.id, name="Local", slug="local")
    away = Team(season_id=season.id, name="Visitante", slug="visitante")
    db.add_all([home, away])
    await db.flush()
    days = [Matchday(season_id=season.id, number=n, status="finished") for n in (1, 2, 3)]
    upcoming = Matchday(season_id=season.id, number=4, status="pending")
    db.add_all([*days, upcoming])
    await db.flush()
    db.add_all(
        [
            Match(
                matchday_id=d.id,
                home_team_id=home.id,
                away_team_id=away.id,
                home_score=1,
                away_score=1,
            )
            for d in days
        ]
        + [Match(matchday_id=upcoming.id, home_team_id=home.id, away_team_id=away.id)]
    )

    def player(name: str) -> Player:
        p = Player(
            season_id=season.id,
            team_id=home.id,
            name=name,
            display_name=name,
            slug=name.lower(),
            position="MED",
        )
        db.add(p)
        return p

    rotates, always = player("Rota"), player("Siempre")
    await db.flush()
    # Starts (45+ minutes) two of his three matches; the other starts all three.
    for p, minutes in ((rotates, (90, 30, 90)), (always, (90, 90, 90))):
        for d, played_minutes, points in zip(days, minutes, (6, 2, 7), strict=True):
            db.add(
                PlayerStat(
                    player_id=p.id,
                    matchday_id=d.id,
                    position="MED",
                    played=True,
                    minutes_played=played_minutes,
                    pts_total=points,
                )
            )
    await db.flush()

    forecast = await AdvancedStatsService(db).get_predictions(season.id, 4)
    by_name = {p.player_name: p for p in forecast.predictions}

    r = by_name["Rota"]
    assert r.starter_pct == 67
    assert r.xpts_if_plays > r.xpts
    assert abs(r.xpts - r.xpts_if_plays * r.starter_pct / 100) <= 0.1

    s = by_name["Siempre"]
    assert s.starter_pct == 100
    assert s.xpts_if_plays == s.xpts
