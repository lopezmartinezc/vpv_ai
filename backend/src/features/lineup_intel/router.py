from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineup_intel.schemas import LineupIntelResponse, RefreshResponse, SourceSummary
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
    """What futbolfantasy and analiticafantasy say about each player. Admin only."""
    return await LineupIntelService(db).read(season_id, matchday)


@router.post("/{season_id}/{matchday}/refresh", response_model=RefreshResponse)
async def refresh_availability(
    season_id: int,
    matchday: int,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
) -> RefreshResponse:
    """Read both sources now. Admin only, and at most once every 10 minutes."""
    claim_manual_refresh(season_id, matchday, datetime.now(UTC))
    results = await LineupIntelService(db).refresh(season_id, matchday)
    return RefreshResponse(
        sources={name: SourceSummary(**asdict(result)) for name, result in results.items()}
    )
