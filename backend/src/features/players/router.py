from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.players.schemas import (
    PlayerListResponse,
    PlayerUpdateRequest,
    PlayerUpdateResponse,
    TeamOption,
)
from src.features.players.service import PlayerService
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/players", tags=["players"])


def _get_service(db: AsyncSession = Depends(get_db)) -> PlayerService:
    return PlayerService(db)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("/teams/{season_id}", response_model=list[TeamOption])
async def list_teams(
    season_id: int,
    service: PlayerService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> list[TeamOption]:
    return await service.list_teams(season_id)


@router.get("/{season_id}", response_model=PlayerListResponse)
async def list_players(
    season_id: int,
    search: str | None = Query(default=None),
    team_id: int | None = Query(default=None),
    service: PlayerService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> PlayerListResponse:
    return await service.list_players(season_id, search, team_id)


@router.patch("/{player_id}", response_model=PlayerUpdateResponse)
async def update_player(
    player_id: int,
    body: PlayerUpdateRequest,
    service: PlayerService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> PlayerUpdateResponse:
    return await service.update_player(player_id, body.team_id, body.position)
