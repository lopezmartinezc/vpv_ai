from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.features.copa.schemas import CopaFullResponse
from src.features.copa.service import CopaService

router = APIRouter(prefix="/copa", tags=["copa"])


def _get_service(db: AsyncSession = Depends(get_db)) -> CopaService:
    return CopaService(db)


@router.get("/{season_id}", response_model=CopaFullResponse)
async def get_copa(
    season_id: int,
    service: CopaService = Depends(_get_service),
) -> CopaFullResponse:
    return await service.get_copa_full(season_id)
