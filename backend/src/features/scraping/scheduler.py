"""APScheduler-based automatic scraping scheduler.

A single ``AsyncIOScheduler`` job fires every ``scraping_poll_interval_seconds``.
An ``asyncio.Lock`` prevents tick overlap.

Per-match CRC change detection:
  For each played match, fetches its match page on futbolfantasy.com and computes
  a CRC from ``modo-picas`` + ``cronistas-marca`` ratings.  Only matches whose
  CRC changed since the last check are re-scraped.

Daily calendar sync:
  A ``cron`` job runs once per day at 06:00 UTC to refresh match dates
  (La Liga frequently reschedules matches).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.database import AsyncSessionLocal
from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.config import scraping_settings
from src.features.scraping.parsers import parse_match_crc
from src.features.scraping.repository import ScrapingRepository
from src.features.scraping.service import ScrapingService

logger = logging.getLogger(__name__)

_scrape_lock = asyncio.Lock()
_scheduler: AsyncIOScheduler | None = None
_last_tick_at: datetime | None = None
_last_calendar_sync_at: datetime | None = None


# ---------------------------------------------------------------------------
# Core tick
# ---------------------------------------------------------------------------


async def _tick() -> None:
    """Scheduler entry point.  Skips if the previous tick is still running."""
    if _scrape_lock.locked():
        logger.info("scheduler.tick: previous tick still running, skipping")
        return

    async with _scrape_lock:
        try:
            await _run_tick()
        except asyncio.CancelledError:
            logger.info("scheduler.tick: cancelled (shutdown), exiting gracefully")
            raise


async def _run_tick() -> None:
    global _last_tick_at
    _last_tick_at = datetime.now(UTC)
    logger.info("scheduler.tick: starting")

    async with AsyncSessionLocal() as session:
        try:
            repo = ScrapingRepository(session)
            service = ScrapingService(session)

            # 1. Active season
            season = await repo.get_active_season()
            if season is None:
                logger.info("scheduler.tick: no active season, skipping")
                return

            season_id = season.id
            md_current = season.matchday_current
            if md_current == 0:
                logger.info("scheduler.tick: matchday_current=0, skipping")
                return

            # 2. Update calendar first — populates match scores and dates.
            try:
                cal_result = await service.scrape_calendar(season_id)
                if cal_result["scores_updated"] or cal_result["dates_updated"]:
                    logger.info("scheduler.tick: calendar %s", cal_result)
                    await session.commit()
            except Exception:
                logger.exception("scheduler.tick: error updating calendar")

            # 3. Load matchday + matches (re-read after calendar update)
            matchday = await repo.get_matchday(season_id, md_current)
            if matchday is None:
                logger.info(
                    "scheduler.tick: matchday not found season=%d number=%d",
                    season_id,
                    md_current,
                )
                return

            matches = await repo.get_matches_for_matchday(matchday.id)
            if not matches:
                logger.info("scheduler.tick: no matches in matchday %d", matchday.id)
                return

            # 4. Filter played matches (have a result + source_url for CRC check)
            played = [m for m in matches if m.source_url is not None and m.home_score is not None]
            if not played:
                logger.info("scheduler.tick: no matches played yet, skipping")
                return

            logger.info(
                "scheduler.tick: %d/%d matches played, checking CRCs",
                len(played),
                len(matches),
            )

            # 5. Per-match CRC check
            matches_to_scrape: list[int] = []

            async with ScrapingClient() as client:
                for match in played:
                    try:
                        html = await client.fetch(match.source_url)  # type: ignore[arg-type]
                    except ScrapingError:
                        logger.warning(
                            "scheduler.tick: failed to fetch match page id=%d url=%s",
                            match.id,
                            match.source_url,
                        )
                        continue

                    new_crc = parse_match_crc(html)

                    if match.stats_crc == new_crc:
                        logger.debug(
                            "scheduler.tick: match %d CRC unchanged (%s)",
                            match.id,
                            new_crc,
                        )
                        continue

                    logger.info(
                        "scheduler.tick: match %d CRC changed %s -> %s",
                        match.id,
                        match.stats_crc,
                        new_crc,
                    )
                    await repo.update_match_crc(match.id, new_crc)
                    matches_to_scrape.append(match.id)

            if not matches_to_scrape:
                logger.info("scheduler.tick: all CRCs unchanged, nothing to scrape")
                await session.commit()
                return

            # 6. Scrape changed matches
            logger.info(
                "scheduler.tick: scraping %d matches: %s",
                len(matches_to_scrape),
                matches_to_scrape,
            )
            for match_id in matches_to_scrape:
                try:
                    result = await service.scrape_match_players(
                        season_id,
                        md_current,
                        match_id,
                    )
                    logger.info(
                        "scheduler.tick: scraped match %d: %s",
                        match_id,
                        result,
                    )
                except Exception:
                    logger.exception(
                        "scheduler.tick: error scraping match %d",
                        match_id,
                    )

            await session.commit()
            logger.info("scheduler.tick: committed successfully")

        except Exception:
            await session.rollback()
            logger.exception("scheduler.tick: unhandled error, rolled back")


# ---------------------------------------------------------------------------
# Lineup deadline check (every 60 seconds)
# ---------------------------------------------------------------------------

_last_deadline_matchday: int | None = None  # track last processed matchday


async def _deadline_check() -> None:
    """Check if the lineup deadline has passed and copy previous lineups."""
    global _last_deadline_matchday

    async with AsyncSessionLocal() as session:
        try:
            from src.features.lineups.repository import LineupRepository
            from src.features.lineups.service import LineupService

            repo = LineupRepository(session)
            scraping_repo = ScrapingRepository(session)

            season = await scraping_repo.get_active_season()
            if season is None:
                return

            md_number = season.matchday_current
            if md_number == 0:
                return

            # Already processed this matchday
            if _last_deadline_matchday == md_number:
                return

            matchday = await repo.get_matchday(season.id, md_number)
            if matchday is None:
                return

            # Compute deadline
            deadline = matchday.deadline_at
            if deadline is None and matchday.first_match_at is not None:
                from datetime import timedelta

                deadline = matchday.first_match_at - timedelta(minutes=season.lineup_deadline_min)

            if deadline is None:
                return

            from datetime import datetime

            now = datetime.now(UTC)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)

            if now < deadline:
                return  # Deadline not reached yet

            logger.info(
                "scheduler.deadline_check: deadline passed for matchday %d, applying auto-copy",
                md_number,
            )
            service = LineupService(session)
            result = await service.apply_deadline_lineups(season.id, md_number)
            await session.commit()
            _last_deadline_matchday = md_number
            logger.info("scheduler.deadline_check: done — %s", result)

        except Exception:
            await session.rollback()
            logger.exception("scheduler.deadline_check: error")


# ---------------------------------------------------------------------------
# Daily calendar sync
# ---------------------------------------------------------------------------


async def _calendar_sync() -> None:
    """Fetch the La Liga calendar and update match dates + scores."""
    global _last_calendar_sync_at
    logger.info("scheduler.calendar_sync: starting")
    _last_calendar_sync_at = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        try:
            repo = ScrapingRepository(session)
            service = ScrapingService(session)

            season = await repo.get_active_season()
            if season is None:
                logger.info("scheduler.calendar_sync: no active season, skipping")
                return

            result = await service.scrape_calendar(season.id)
            await session.commit()
            logger.info("scheduler.calendar_sync: done — %s", result)

        except Exception:
            await session.rollback()
            logger.exception("scheduler.calendar_sync: error")


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


def start_scheduler() -> None:
    """Create and start the AsyncIOScheduler.  Idempotent."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("scheduler.start: already running")
        return

    interval = scraping_settings.scraping_poll_interval_seconds
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _tick,
        trigger="interval",
        seconds=interval,
        id="scraping_tick",
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=60,
    )
    _scheduler.add_job(
        _calendar_sync,
        trigger="cron",
        hour=6,
        minute=0,
        id="calendar_sync",
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _deadline_check,
        trigger="interval",
        seconds=60,
        id="deadline_check",
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=30,
    )
    _scheduler.start()
    logger.info(
        "scheduler.start: started, tick_interval=%ds, calendar_sync=daily@06:00, deadline_check=60s",
        interval,
    )


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("scheduler.stop: stopped")


def get_scheduler_status() -> dict:
    """Return current scheduler state for admin dashboard."""
    running = _scheduler is not None and _scheduler.running
    next_run: str | None = None
    next_calendar_sync: str | None = None

    if running and _scheduler is not None:
        job = _scheduler.get_job("scraping_tick")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
        cal_job = _scheduler.get_job("calendar_sync")
        if cal_job and cal_job.next_run_time:
            next_calendar_sync = cal_job.next_run_time.isoformat()

    return {
        "running": running,
        "poll_interval_seconds": scraping_settings.scraping_poll_interval_seconds,
        "last_tick_at": _last_tick_at.isoformat() if _last_tick_at else None,
        "next_run_at": next_run,
        "lock_held": _scrape_lock.locked(),
        "last_calendar_sync_at": _last_calendar_sync_at.isoformat()
        if _last_calendar_sync_at
        else None,
        "next_calendar_sync_at": next_calendar_sync,
    }


async def trigger_tick() -> dict:
    """Manually trigger a single scheduler tick.  Returns status."""
    if _scrape_lock.locked():
        return {"triggered": False, "reason": "previous tick still running"}

    _background_task = asyncio.create_task(_tick())  # noqa: RUF006
    return {"triggered": True}
