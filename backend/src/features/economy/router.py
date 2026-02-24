from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.economy.schemas import EconomyResponse, ParticipantEconomyResponse
from src.features.economy.service import EconomyService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/economy", tags=["economy"])


def _get_service(db: AsyncSession = Depends(get_db)) -> EconomyService:
    return EconomyService(db)


@router.get("/{season_id}", response_model=EconomyResponse)
async def get_economy_overview(
    season_id: int,
    service: EconomyService = Depends(_get_service),
) -> EconomyResponse:
    return await service.get_overview(season_id)


@router.get("/{season_id}/{participant_id}", response_model=ParticipantEconomyResponse)
async def get_participant_transactions(
    season_id: int,
    participant_id: int,
    service: EconomyService = Depends(_get_service),
) -> ParticipantEconomyResponse:
    return await service.get_participant_transactions(season_id, participant_id)
