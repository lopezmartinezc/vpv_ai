from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.economy.schemas import (
    EconomyResponse,
    ParticipantEconomyResponse,
    TransactionCreateRequest,
    TransactionEntry,
)
from src.features.economy.service import EconomyService
from src.shared.dependencies import get_current_admin, get_db

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


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/admin/{season_id}/transaction",
    response_model=TransactionEntry,
)
async def create_transaction(
    season_id: int,
    body: TransactionCreateRequest,
    service: EconomyService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> TransactionEntry:
    return await service.create_transaction(
        season_id=season_id,
        participant_id=body.participant_id,
        tx_type=body.type,
        amount=body.amount,
        description=body.description,
        matchday_id=body.matchday_id,
    )


@router.delete(
    "/admin/{season_id}/transaction/{tx_id}",
)
async def delete_transaction(
    season_id: int,
    tx_id: int,
    service: EconomyService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> dict:
    await service.delete_transaction(season_id, tx_id)
    return {"deleted": True}
