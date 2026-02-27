from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineups.schemas import LineupSubmitRequest, LineupSubmitResponse
from src.features.lineups.service import LineupService
from src.shared.dependencies import get_current_admin, get_current_user, get_db

router = APIRouter(prefix="/lineups", tags=["lineups"])


def _get_service(db: AsyncSession = Depends(get_db)) -> LineupService:
    return LineupService(db)


@router.post(
    "/{season_id}/{matchday_number}",
    response_model=LineupSubmitResponse,
)
async def submit_lineup(
    season_id: int,
    matchday_number: int,
    data: LineupSubmitRequest,
    user: dict = Depends(get_current_user),
    service: LineupService = Depends(_get_service),
) -> LineupSubmitResponse:
    """Submit or update lineup for the current matchday."""
    return await service.submit_lineup(
        user_id=int(user["sub"]),
        season_id=season_id,
        matchday_number=matchday_number,
        data=data,
    )


@router.post(
    "/admin/{season_id}/{matchday_number}/apply-deadline",
)
async def apply_deadline_lineups(
    season_id: int,
    matchday_number: int,
    _admin: dict = Depends(get_current_admin),
    service: LineupService = Depends(_get_service),
) -> dict:
    """Copy previous lineup for participants who missed the deadline."""
    return await service.apply_deadline_lineups(season_id, matchday_number)
