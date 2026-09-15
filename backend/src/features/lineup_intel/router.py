from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineup_intel import service as intel_service
from src.features.lineup_intel.schemas import LineupIntelResponse, RefreshStarted
from src.features.lineup_intel.service import LineupIntelService, claim_manual_refresh
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/lineup-intel", tags=["lineup-intel"])


@router.get("/{season_id}/{matchday}", response_model=LineupIntelResponse)
async def read_availability(
    season_id: int,
    matchday: int,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
) -> LineupIntelResponse:
    """What the probable-lineup sources say about each player. Admin only."""
    return await LineupIntelService(db).read(season_id, matchday)


@router.post("/{season_id}/{matchday}/refresh", response_model=RefreshStarted, status_code=202)
async def refresh_availability(
    season_id: int,
    matchday: int,
    admin: dict = Depends(get_current_admin),
) -> RefreshStarted:
    """Read every source now, predicted11 included, in the background. Admin
    only, and at most once every 10 minutes. The screen reads the availability
    again until its time changes."""
    claim_manual_refresh(season_id, matchday, datetime.now(UTC))
    intel_service.start_background_refresh(season_id, matchday)
    return RefreshStarted()
