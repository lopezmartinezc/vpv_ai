from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.scraping.scheduler import (
    get_scheduler_status,
    start_scheduler,
    stop_scheduler,
    trigger_calendar_sync,
    trigger_deadline_check,
    trigger_tick,
)
from src.features.scraping.service import ScrapingService
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/scraping", tags=["scraping"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ScrapingService:
    """Dependency factory: creates a ``ScrapingService`` bound to the request session."""
    return ScrapingService(db)


@router.post(
    "/matchday/{season_id}/{number}",
    summary="Scrape all player stats for a matchday",
)
async def scrape_matchday_endpoint(
    season_id: int,
    number: int,
    _admin: dict = Depends(get_current_admin),
    service: ScrapingService = Depends(_get_service),
) -> dict:
    """Trigger a full scrape of player stats for the given matchday.

    Processes all counting matches in the matchday sequentially (one HTTP
    request per player).  Returns a summary of processed / skipped / error
    counts.
    """
    return await service.scrape_matchday(season_id, number)


@router.post(
    "/match/{season_id}/{number}/{match_id}",
    summary="Scrape stats for a single match",
)
async def scrape_match_endpoint(
    season_id: int,
    number: int,
    match_id: int,
    _admin: dict = Depends(get_current_admin),
    service: ScrapingService = Depends(_get_service),
) -> dict:
    """Trigger a scrape of player stats for a single match.

    Useful for re-scraping an individual match without touching the rest of
    the matchday.  Returns a summary of processed / skipped / error counts.
    """
    return await service.scrape_match_players(season_id, number, match_id)


@router.post(
    "/calendar/{season_id}",
    summary="Update match scores and dates from La Liga calendar",
    response_model=dict,
)
async def scrape_calendar_endpoint(
    season_id: int,
    _admin: dict = Depends(get_current_admin),
    service: ScrapingService = Depends(_get_service),
) -> dict[str, int]:
    """Fetch the La Liga calendar page and update DB match scores and dates.

    Returns the number of scores and dates updated.
    """
    return await service.scrape_calendar(season_id)


@router.post(
    "/check-updates",
    summary="Check homepage CRC for new stats",
    response_model=dict,
)
async def check_updates_endpoint(
    _admin: dict = Depends(get_current_admin),
    service: ScrapingService = Depends(_get_service),
) -> dict:
    """Check whether the futbolfantasy homepage CRC has changed.

    When the CRC differs from the last saved value it means new match stats
    are available.  Returns ``changed=True`` and the list of ready match IDs.
    """
    match_ids = await service.check_for_updates()
    return {"changed": len(match_ids) > 0, "ready_match_ids": match_ids}


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/admin/status",
    summary="Get scheduler status",
    response_model=dict,
)
async def scheduler_status(
    _admin: dict = Depends(get_current_admin),
) -> dict:
    return get_scheduler_status()


@router.post(
    "/admin/trigger",
    summary="Trigger a manual scheduler tick",
    response_model=dict,
)
async def scheduler_trigger(
    _admin: dict = Depends(get_current_admin),
) -> dict:
    return await trigger_tick()


@router.post(
    "/admin/trigger/calendar-sync",
    summary="Trigger calendar sync",
    response_model=dict,
)
async def scheduler_trigger_calendar(
    _admin: dict = Depends(get_current_admin),
) -> dict:
    """Manually fire a calendar sync outside the daily cron schedule."""
    return await trigger_calendar_sync()


@router.post(
    "/admin/trigger/deadline-check",
    summary="Trigger deadline check",
    response_model=dict,
)
async def scheduler_trigger_deadline(
    _admin: dict = Depends(get_current_admin),
) -> dict:
    """Manually fire a deadline check outside the 60-second interval."""
    return await trigger_deadline_check()


@router.post(
    "/admin/start",
    summary="Start the scheduler",
    response_model=dict,
)
async def scheduler_start(
    _admin: dict = Depends(get_current_admin),
) -> dict:
    start_scheduler()
    return get_scheduler_status()


@router.post(
    "/admin/stop",
    summary="Stop the scheduler",
    response_model=dict,
)
async def scheduler_stop(
    _admin: dict = Depends(get_current_admin),
) -> dict:
    stop_scheduler()
    return get_scheduler_status()
