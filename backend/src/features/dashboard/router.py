from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query

from src.core.database import AsyncSessionLocal
from src.core.exceptions import NotFoundError
from src.features.copa.service import CopaService
from src.features.dashboard.schemas import DashboardResponse
from src.features.economy.service import EconomyService
from src.features.matchdays.service import MatchdayService
from src.features.standings.service import StandingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# The blocks of the home page, in the order they are fetched.
SECTIONS = ("standings", "current_matchday", "copa", "economy")


def settle(name: str, result: object, season_id: int) -> tuple[object | None, bool]:
    """One section's value, and whether it failed.

    Absent and broken used to look the same: every exception became None, with
    no log, and the home page showed an empty block as though there were simply
    no data (IN-02). A missing resource — a season with no copa, a jornada that
    does not exist yet — is absence. Anything else is a failure: logged, and
    named in ``unavailable`` so the page can say it could not load that part
    instead of showing nothing.
    """
    if isinstance(result, NotFoundError):
        return None, False
    if isinstance(result, BaseException):
        logger.error(
            "dashboard: section %s failed for season_id=%d", name, season_id, exc_info=result
        )
        return None, True
    return result, False


@router.get("/{season_id}", response_model=DashboardResponse)
async def get_dashboard(
    season_id: int,
    matchday_current: int | None = Query(None),
) -> DashboardResponse:
    """Combined dashboard data in a single request (parallel DB queries).

    Sections load independently, so one failing does not take the others down.
    The ones that failed are listed in ``unavailable``.
    """

    async def fetch_standings() -> object:
        async with AsyncSessionLocal() as s:
            return await StandingsService(s).get_standings(season_id)

    async def fetch_matchday() -> object:
        if matchday_current is None:
            return None
        async with AsyncSessionLocal() as s:
            return await MatchdayService(s).get_matchday_detail(season_id, matchday_current)

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

    values: dict[str, object | None] = {}
    unavailable: list[str] = []
    for name, result in zip(SECTIONS, results, strict=True):
        value, failed = settle(name, result, season_id)
        values[name] = value
        if failed:
            unavailable.append(name)
    return DashboardResponse(**values, unavailable=unavailable)
