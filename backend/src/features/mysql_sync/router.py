"""Admin endpoint: push matchday data from PostgreSQL to legacy MySQL."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.mysql_sync.service import MysqlSyncService
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/mysql-sync", tags=["mysql-sync"])


class SyncResponse(BaseModel):
    matchday_number: int
    season_name: str
    stats_upserted: int
    lineups_upserted: int
    errors: list[str]


@router.post(
    "/admin/{season_id}/{matchday_number}",
    response_model=SyncResponse,
)
async def reverse_sync_matchday(
    season_id: int,
    matchday_number: int,
    _admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """Push matchday data (stats + lineups) from PostgreSQL to legacy MySQL."""
    svc = MysqlSyncService(db)
    result = await svc.reverse_sync_matchday(season_id, matchday_number)
    return SyncResponse(
        matchday_number=result.matchday_number,
        season_name=result.season_name,
        stats_upserted=result.stats_upserted,
        lineups_upserted=result.lineups_upserted,
        errors=result.errors,
    )
