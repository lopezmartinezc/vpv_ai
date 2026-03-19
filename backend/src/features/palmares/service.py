from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.palmares.repository import PalmaresRepository
from src.features.palmares.schemas import (
    AllTimeRecord,
    CareerEntry,
    PalmaresResponse,
    PodiumEntry,
    SeasonChampion,
)


class PalmaresService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PalmaresRepository(session)

    async def get_palmares(self) -> PalmaresResponse:
        all_standings = await self.repo.get_all_standings()

        # 1. Build champions (podium per season)
        seasons_map: dict[int, SeasonChampion] = {}
        for row in all_standings:
            if row.season_id not in seasons_map:
                seasons_map[row.season_id] = SeasonChampion(
                    season_id=row.season_id,
                    season_name=row.season_name,
                    entries=[],
                )
            if row.rank <= 3:
                seasons_map[row.season_id].entries.append(
                    PodiumEntry(
                        rank=row.rank,
                        user_id=row.user_id,
                        display_name=row.display_name,
                        total_points=row.total_points,
                        matchdays_played=row.matchdays_played,
                    )
                )

        champions = list(seasons_map.values())

        # 2. Build career stats per user
        user_stats: dict[int, dict] = {}
        for row in all_standings:
            if row.user_id not in user_stats:
                user_stats[row.user_id] = {
                    "display_name": row.display_name,
                    "seasons_played": 0,
                    "championships": 0,
                    "podiums": 0,
                    "total_points": 0,
                    "total_matchdays": 0,
                    "best_finish": 999,
                    "best_season_name": "",
                    "season_ids": set(),
                }

            stats = user_stats[row.user_id]
            stats["display_name"] = row.display_name  # use latest name

            if row.season_id not in stats["season_ids"]:
                stats["season_ids"].add(row.season_id)
                stats["seasons_played"] += 1

            stats["total_points"] += row.total_points
            stats["total_matchdays"] += row.matchdays_played

            if row.rank == 1:
                stats["championships"] += 1
            if row.rank <= 3:
                stats["podiums"] += 1
            if row.rank < stats["best_finish"]:
                stats["best_finish"] = row.rank
                stats["best_season_name"] = row.season_name

        career = sorted(
            [
                CareerEntry(
                    user_id=uid,
                    display_name=s["display_name"],
                    seasons_played=s["seasons_played"],
                    championships=s["championships"],
                    podiums=s["podiums"],
                    total_points=s["total_points"],
                    total_matchdays=s["total_matchdays"],
                    avg_points=round(s["total_points"] / s["total_matchdays"], 1)
                    if s["total_matchdays"] > 0
                    else 0,
                    best_finish=s["best_finish"] if s["best_finish"] < 999 else 0,
                    best_season_name=s["best_season_name"],
                )
                for uid, s in user_stats.items()
            ],
            key=lambda c: c.championships * 10000 + c.podiums * 1000 + c.total_points,
            reverse=True,
        )

        # 3. All-time records
        records: list[AllTimeRecord] = []

        best = await self.repo.get_best_matchday_score()
        if best:
            records.append(
                AllTimeRecord(
                    label="Mayor puntuacion en una jornada",
                    value=f"{best.total_points} pts",
                    detail=f"{best.display_name} — J{best.matchday_number} ({best.season_name})",
                )
            )

        worst = await self.repo.get_worst_matchday_score()
        if worst:
            records.append(
                AllTimeRecord(
                    label="Menor puntuacion en una jornada",
                    value=f"{worst.total_points} pts",
                    detail=f"{worst.display_name} — J{worst.matchday_number} ({worst.season_name})",
                )
            )

        # Best season avg
        if career:
            best_avg_user = max(
                (c for c in career if c.total_matchdays >= 10),
                key=lambda c: c.avg_points,
                default=None,
            )
            if best_avg_user:
                records.append(
                    AllTimeRecord(
                        label="Mejor media historica",
                        value=f"{best_avg_user.avg_points} pts/jornada",
                        detail=f"{best_avg_user.display_name} ({best_avg_user.total_matchdays} jornadas)",
                    )
                )

            # Most championships
            most_titles = max(career, key=lambda c: c.championships, default=None)
            if most_titles and most_titles.championships > 0:
                records.append(
                    AllTimeRecord(
                        label="Mas campeonatos",
                        value=f"{most_titles.championships} titulos",
                        detail=most_titles.display_name,
                    )
                )

        return PalmaresResponse(
            champions=champions,
            career=career,
            records=records,
        )
