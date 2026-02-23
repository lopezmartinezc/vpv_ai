from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.seasons.repository import SeasonRepository
from src.features.standings.repository import StandingsRepository
from src.features.standings.schemas import StandingEntry, StandingsResponse


class StandingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.standings_repo = StandingsRepository(session)
        self.season_repo = SeasonRepository(session)

    async def get_standings(self, season_id: int) -> StandingsResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        rows = await self.standings_repo.get_standings(season_id)
        entries = [
            StandingEntry(
                rank=i + 1,
                participant_id=row.participant_id,
                display_name=row.display_name,
                total_points=row.total_points,
                matchdays_played=row.matchdays_played,
                avg_points=round(row.total_points / row.matchdays_played, 1)
                if row.matchdays_played > 0
                else 0.0,
            )
            for i, row in enumerate(rows)
        ]
        return StandingsResponse(
            season_id=season.id,
            season_name=season.name,
            entries=entries,
        )
