from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.matchdays.schemas import (
    LineupDetailResponse,
    MatchdayDetailResponse,
    MatchdayListResponse,
)
from src.features.matchdays.service import MatchdayService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/matchdays", tags=["matchdays"])


def _get_service(db: AsyncSession = Depends(get_db)) -> MatchdayService:
    return MatchdayService(db)


@router.get("/{season_id}", response_model=MatchdayListResponse)
async def list_matchdays(
    season_id: int,
    stats_ok_only: bool = Query(default=True),
    service: MatchdayService = Depends(_get_service),
) -> MatchdayListResponse:
    return await service.list_matchdays(
        season_id, stats_ok_only=stats_ok_only,
    )


@router.get("/{season_id}/{number}", response_model=MatchdayDetailResponse)
async def get_matchday_detail(
    season_id: int,
    number: int,
    service: MatchdayService = Depends(_get_service),
) -> MatchdayDetailResponse:
    return await service.get_matchday_detail(season_id, number)


@router.get(
    "/{season_id}/{number}/lineup/{participant_id}",
    response_model=LineupDetailResponse,
)
async def get_lineup_detail(
    season_id: int,
    number: int,
    participant_id: int,
    service: MatchdayService = Depends(_get_service),
) -> LineupDetailResponse:
    return await service.get_lineup_detail(season_id, number, participant_id)
