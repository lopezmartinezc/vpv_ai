from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.seasons.repository import SeasonRepository
from src.features.squads.repository import SquadRepository
from src.features.squads.schemas import (
    PositionCounts,
    SquadDetailResponse,
    SquadListResponse,
    SquadPlayerEntry,
    SquadSummary,
)


class SquadService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = SquadRepository(session)
        self.season_repo = SeasonRepository(session)

    async def list_squads(self, season_id: int) -> SquadListResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        rows = await self.repo.list_squads(season_id)
        return SquadListResponse(
            season_id=season_id,
            squads=[
                SquadSummary(
                    participant_id=r.participant_id,
                    display_name=r.display_name,
                    total_players=r.total_players,
                    season_points=r.season_points,
                    positions=PositionCounts(
                        POR=r.por, DEF=r.defe, MED=r.med, DEL=r.dele,
                    ),
                )
                for r in rows
            ],
        )

    async def get_squad_detail(
        self, season_id: int, participant_id: int,
    ) -> SquadDetailResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        display_name = await self.repo.get_participant_display_name(participant_id)
        if display_name is None:
            raise NotFoundError("Participant", participant_id)

        season_points = await self.repo.get_participant_season_points(
            season_id, participant_id,
        )
        player_rows = await self.repo.get_squad_players(season_id, participant_id)

        return SquadDetailResponse(
            participant_id=participant_id,
            display_name=display_name,
            season_points=season_points,
            players=[
                SquadPlayerEntry(
                    player_id=p.player_id,
                    display_name=p.display_name,
                    position=p.position,
                    team_name=p.team_name,
                    season_points=p.season_points,
                )
                for p in player_rows
            ],
        )
