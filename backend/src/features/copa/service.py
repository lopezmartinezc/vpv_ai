from __future__ import annotations

from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.copa.repository import CopaRepository
from src.features.copa.schemas import (
    CopaFullResponse,
    CopaMatchdayDetail,
    CopaMatchdayResult,
    CopaStandingEntry,
)
from src.features.seasons.repository import SeasonRepository


class CopaService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CopaRepository(session)
        self.season_repo = SeasonRepository(session)

    async def get_copa_full(self, season_id: int) -> CopaFullResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        raw_rows = await self.repo.get_copa_data(season_id)

        # Build per-matchday results and accumulate standings
        matchday_map: dict[int, list[CopaMatchdayResult]] = defaultdict(list)
        totals: dict[int, dict] = {}

        for row in raw_rows:
            gf = row.goals_for
            ga = row.goals_against
            gd = gf - ga

            if gf > ga:
                pts = 3
            elif gf == ga:
                pts = 1
            else:
                pts = 0

            matchday_map[row.matchday_number].append(
                CopaMatchdayResult(
                    participant_id=row.participant_id,
                    display_name=row.display_name,
                    goals_for=gf,
                    goals_against=ga,
                    goal_difference=gd,
                    points=pts,
                )
            )

            if row.participant_id not in totals:
                totals[row.participant_id] = {
                    "display_name": row.display_name,
                    "total_points": 0,
                    "matches_played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "total_goals_for": 0,
                    "total_goals_against": 0,
                }

            t = totals[row.participant_id]
            t["total_points"] += pts
            t["matches_played"] += 1
            t["total_goals_for"] += gf
            t["total_goals_against"] += ga
            if pts == 3:
                t["wins"] += 1
            elif pts == 1:
                t["draws"] += 1
            else:
                t["losses"] += 1

        # Sort matchday results by points DESC, goal_difference DESC
        for md_results in matchday_map.values():
            md_results.sort(key=lambda r: (-r.points, -r.goal_difference))

        # Build standings sorted by total_points DESC, goal_difference DESC
        standings_list = []
        for pid, t in totals.items():
            gd = t["total_goals_for"] - t["total_goals_against"]
            standings_list.append((pid, t, gd))

        standings_list.sort(key=lambda x: (-x[1]["total_points"], -x[2]))

        standings = [
            CopaStandingEntry(
                rank=i + 1,
                participant_id=pid,
                display_name=t["display_name"],
                total_points=t["total_points"],
                matches_played=t["matches_played"],
                wins=t["wins"],
                draws=t["draws"],
                losses=t["losses"],
                total_goals_for=t["total_goals_for"],
                total_goals_against=t["total_goals_against"],
                goal_difference=gd,
            )
            for i, (pid, t, gd) in enumerate(standings_list)
        ]

        matchdays = [
            CopaMatchdayDetail(
                matchday_number=md_num,
                results=matchday_map[md_num],
            )
            for md_num in sorted(matchday_map.keys())
        ]

        return CopaFullResponse(
            season_id=season_id,
            season_name=season.name,
            standings=standings,
            matchdays=matchdays,
        )
