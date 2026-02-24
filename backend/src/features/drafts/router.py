from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.drafts.schemas import DraftDetailResponse, DraftListResponse
from src.features.drafts.service import DraftService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _get_service(db: AsyncSession = Depends(get_db)) -> DraftService:
    return DraftService(db)


@router.get("/{season_id}", response_model=DraftListResponse)
async def list_drafts(
    season_id: int,
    service: DraftService = Depends(_get_service),
) -> DraftListResponse:
    return await service.list_drafts(season_id)


@router.get("/{season_id}/{phase}", response_model=DraftDetailResponse)
async def get_draft_detail(
    season_id: int,
    phase: str,
    service: DraftService = Depends(_get_service),
) -> DraftDetailResponse:
    return await service.get_draft_detail(season_id, phase)
