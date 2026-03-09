from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.players.repository import PlayerRepository
from src.features.players.schemas import (
    PlayerListItem,
    PlayerListResponse,
    PlayerUpdateResponse,
    TeamOption,
)


class PlayerService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PlayerRepository(session)

    async def list_players(
        self,
        season_id: int,
        search: str | None,
        team_id: int | None,
    ) -> PlayerListResponse:
        rows = await self.repo.list_players(season_id, search, team_id)
        return PlayerListResponse(
            season_id=season_id,
            players=[
                PlayerListItem(
                    id=r.id,
                    display_name=r.display_name,
                    slug=r.slug,
                    position=r.position,
                    team_id=r.team_id,
                    team_name=r.team_name,
                    owner_name=r.owner_name,
                    is_available=r.is_available,
                )
                for r in rows
            ],
            total=len(rows),
        )

    async def list_teams(self, season_id: int) -> list[TeamOption]:
        teams = await self.repo.list_teams(season_id)
        return [TeamOption(id=t.id, name=t.name) for t in teams]

    async def update_player(
        self,
        player_id: int,
        team_id: int | None,
        position: str | None,
    ) -> PlayerUpdateResponse:
        player = await self.repo.get_player_detail(player_id)
        if player is None:
            raise NotFoundError("Player", player_id)

        if team_id is not None:
            belongs = await self.repo.team_belongs_to_season(team_id, player.season_id)
            if not belongs:
                raise BusinessRuleError(
                    f"El equipo {team_id} no pertenece a la temporada {player.season_id}"
                )

        await self.repo.update_player(player_id, team_id, position)

        updated = await self.repo.get_updated_player_detail(player_id)
        # updated cannot be None here — we just confirmed the player exists.
        assert updated is not None

        return PlayerUpdateResponse(
            id=updated.id,
            display_name=updated.display_name,
            team_id=updated.team_id,
            team_name=updated.team_name,
            position=updated.position,
        )
