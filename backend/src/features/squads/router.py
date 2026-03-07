from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.squads.schemas import SquadDetailResponse, SquadListResponse
from src.features.squads.service import SquadService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/squads", tags=["squads"])


def _get_service(db: AsyncSession = Depends(get_db)) -> SquadService:
    return SquadService(db)


@router.get("/{season_id}", response_model=SquadListResponse)
async def list_squads(
    season_id: int,
    matchday: int | None = Query(default=None),
    service: SquadService = Depends(_get_service),
) -> SquadListResponse:
    return await service.list_squads(season_id, matchday)


@router.get("/{season_id}/{participant_id}", response_model=SquadDetailResponse)
async def get_squad_detail(
    season_id: int,
    participant_id: int,
    matchday: int | None = Query(default=None),
    service: SquadService = Depends(_get_service),
) -> SquadDetailResponse:
    return await service.get_squad_detail(season_id, participant_id, matchday)
