from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.shared.dependencies import get_db
from src.shared.schemas.health import HealthCheckResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> HealthCheckResponse:
    db_ok = False
    try:
        result = await db.execute(text("SELECT 1"))
        db_ok = result.scalar() == 1
    except Exception:
        db_ok = False

    return HealthCheckResponse(
        status="healthy" if db_ok else "unhealthy",
        database=db_ok,
        version=settings.app_version,
    )
