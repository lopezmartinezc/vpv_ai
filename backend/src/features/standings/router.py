from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.standings.schemas import StandingsResponse
from src.features.standings.service import StandingsService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/standings", tags=["standings"])


def _get_service(db: AsyncSession = Depends(get_db)) -> StandingsService:
    return StandingsService(db)


@router.get("/{season_id}", response_model=StandingsResponse)
async def get_standings(
    season_id: int,
    service: StandingsService = Depends(_get_service),
) -> StandingsResponse:
    return await service.get_standings(season_id)
