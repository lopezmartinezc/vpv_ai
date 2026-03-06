from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from src.core.database import AsyncSessionLocal
from src.features.copa.service import CopaService
from src.features.dashboard.schemas import DashboardResponse
from src.features.economy.service import EconomyService
from src.features.matchdays.service import MatchdayService
from src.features.standings.service import StandingsService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{season_id}", response_model=DashboardResponse)
async def get_dashboard(
    season_id: int,
    matchday_current: int | None = Query(None),
) -> DashboardResponse:
    """Combined dashboard data in a single request (parallel DB queries)."""

    async def fetch_standings() -> object:
        async with AsyncSessionLocal() as s:
            return await StandingsService(s).get_standings(season_id)

    async def fetch_matchday() -> object:
        if matchday_current is None:
            return None
        async with AsyncSessionLocal() as s:
            return await MatchdayService(s).get_matchday_detail(
                season_id, matchday_current
            )

    async def fetch_copa() -> object:
        async with AsyncSessionLocal() as s:
            return await CopaService(s).get_copa_full(season_id)

    async def fetch_economy() -> object:
        async with AsyncSessionLocal() as s:
            return await EconomyService(s).get_overview(season_id)

    results = await asyncio.gather(
        fetch_standings(),
        fetch_matchday(),
        fetch_copa(),
        fetch_economy(),
        return_exceptions=True,
    )

    return DashboardResponse(
        standings=results[0] if not isinstance(results[0], BaseException) else None,
        current_matchday=results[1]
        if not isinstance(results[1], BaseException)
        else None,
        copa=results[2] if not isinstance(results[2], BaseException) else None,
        economy=results[3] if not isinstance(results[3], BaseException) else None,
    )
