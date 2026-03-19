from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.palmares.schemas import PalmaresResponse
from src.features.palmares.service import PalmaresService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/palmares", tags=["palmares"])


def _get_service(db: AsyncSession = Depends(get_db)) -> PalmaresService:
    return PalmaresService(db)


@router.get("", response_model=PalmaresResponse)
async def get_palmares(
    service: PalmaresService = Depends(_get_service),
) -> PalmaresResponse:
    """Historical records and champions across all seasons."""
    return await service.get_palmares()
