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
from collections import deque
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
_last_deadline_check_at: datetime | None = None

# ---------------------------------------------------------------------------
# Per-job log buffer (circular, max 50 entries per job)
# ---------------------------------------------------------------------------
_MAX_LOG_ENTRIES = 50
_job_logs: dict[str, deque[dict]] = {
    "scraping_tick": deque(maxlen=_MAX_LOG_ENTRIES),
    "calendar_sync": deque(maxlen=_MAX_LOG_ENTRIES),
    "deadline_check": deque(maxlen=_MAX_LOG_ENTRIES),
}


def _log(job_id: str, message: str, level: str = "info") -> None:
    """Append a log entry to the per-job buffer and also emit via stdlib logger."""
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "level": level,
        "msg": message,
    }
    _job_logs[job_id].append(entry)
    getattr(logger, level, logger.info)("scheduler.%s: %s", job_id, message)


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
    _log("scraping_tick", "Inicio tick")

    async with AsyncSessionLocal() as session:
        try:
            repo = ScrapingRepository(session)
            service = ScrapingService(session)

            # 1. Active season
            season = await repo.get_active_season()
            if season is None:
                _log("scraping_tick", "Sin temporada activa, omitiendo")
                return

            season_id = season.id
            md_current = season.matchday_current
            if md_current == 0:
                _log("scraping_tick", "matchday_current=0, omitiendo")
                return

            # 2. Update calendar first — populates match scores and dates.
            try:
                cal_result = await service.scrape_calendar(season_id)
                if cal_result["scores_updated"] or cal_result["dates_updated"]:
                    _log("scraping_tick", f"Calendario: {cal_result['scores_updated']} resultados, {cal_result['dates_updated']} fechas")
                    await session.commit()
            except Exception as exc:
                _log("scraping_tick", f"Error calendario: {exc}", "error")

            # 3. Load matchday + matches (re-read after calendar update)
            matchday = await repo.get_matchday(season_id, md_current)
            if matchday is None:
                _log("scraping_tick", f"Jornada {md_current} no encontrada")
                return

            matches = await repo.get_matches_for_matchday(matchday.id)
            if not matches:
                _log("scraping_tick", f"Sin partidos en J{md_current}")
                return

            # 4. Filter played matches (have a result + source_url for CRC check)
            played = [m for m in matches if m.source_url is not None and m.home_score is not None]
            if not played:
                _log("scraping_tick", f"J{md_current}: sin partidos jugados aun")
                return

            _log("scraping_tick", f"J{md_current}: {len(played)}/{len(matches)} partidos jugados, comprobando CRCs")

            # 5. Per-match CRC check
            matches_to_scrape: list[int] = []

            async with ScrapingClient() as client:
                for match in played:
                    try:
                        html = await client.fetch(match.source_url)  # type: ignore[arg-type]
                    except ScrapingError:
                        _log("scraping_tick", f"Error fetch match id={match.id}", "warning")
                        continue

                    new_crc = parse_match_crc(html)

                    if match.stats_crc == new_crc:
                        continue

                    _log("scraping_tick", f"Match {match.id}: CRC cambio {match.stats_crc} -> {new_crc}")
                    await repo.update_match_crc(match.id, new_crc)
                    matches_to_scrape.append(match.id)

            if not matches_to_scrape:
                _log("scraping_tick", "CRCs sin cambios, nada que scrapear")
                await session.commit()
                return

            # 6. Scrape changed matches
            _log("scraping_tick", f"Scrapeando {len(matches_to_scrape)} partidos: {matches_to_scrape}")
            for match_id in matches_to_scrape:
                try:
                    result = await service.scrape_match_players(
                        season_id,
                        md_current,
                        match_id,
                    )
                    _log("scraping_tick", f"Match {match_id}: procesados={result.get('processed', 0)}, errores={result.get('errors', 0)}")
                except Exception as exc:
                    _log("scraping_tick", f"Error scraping match {match_id}: {exc}", "error")

            await session.commit()
            _log("scraping_tick", "Tick completado, cambios guardados")

        except Exception as exc:
            await session.rollback()
            _log("scraping_tick", f"Error fatal: {exc}", "error")


# ---------------------------------------------------------------------------
# Lineup deadline check (every 60 seconds)
# ---------------------------------------------------------------------------

_last_deadline_matchday: int | None = None  # track last processed matchday


async def _deadline_check() -> None:
    """Check if the lineup deadline has passed and copy previous lineups."""
    global _last_deadline_matchday, _last_deadline_check_at
    _last_deadline_check_at = datetime.now(UTC)

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

            _log("deadline_check", f"Deadline J{md_number} superado, copiando alineaciones")
            service = LineupService(session)
            result = await service.apply_deadline_lineups(season.id, md_number)
            await session.commit()
            _last_deadline_matchday = md_number
            _log("deadline_check", f"Auto-copy completado: {result}")

        except Exception as exc:
            await session.rollback()
            _log("deadline_check", f"Error: {exc}", "error")


# ---------------------------------------------------------------------------
# Daily calendar sync
# ---------------------------------------------------------------------------


async def _calendar_sync() -> None:
    """Fetch the La Liga calendar and update match dates + scores."""
    global _last_calendar_sync_at
    _last_calendar_sync_at = datetime.now(UTC)
    _log("calendar_sync", "Inicio sync calendario")

    async with AsyncSessionLocal() as session:
        try:
            repo = ScrapingRepository(session)
            service = ScrapingService(session)

            season = await repo.get_active_season()
            if season is None:
                _log("calendar_sync", "Sin temporada activa, omitiendo")
                return

            result = await service.scrape_calendar(season.id)
            await session.commit()
            _log("calendar_sync", f"Completado: {result['scores_updated']} resultados, {result['dates_updated']} fechas actualizadas")

        except Exception as exc:
            await session.rollback()
            _log("calendar_sync", f"Error: {exc}", "error")


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
    """Return current scheduler state for admin dashboard.

    Includes a ``jobs`` list with per-job detail as well as the legacy flat
    fields so existing callers are not broken.
    """
    running = _scheduler is not None and _scheduler.running

    # --- per-job next_run_time resolution ---
    def _next(job_id: str) -> str | None:
        if not running or _scheduler is None:
            return None
        job = _scheduler.get_job(job_id)
        return job.next_run_time.isoformat() if job and job.next_run_time else None

    next_run = _next("scraping_tick")
    next_calendar_sync = _next("calendar_sync")
    next_deadline_check = _next("deadline_check")

    # --- structured per-job list ---
    jobs: list[dict] = [
        {
            "id": "scraping_tick",
            "name": "Scraping stats",
            "type": "interval",
            "interval_seconds": scraping_settings.scraping_poll_interval_seconds,
            "last_run_at": _last_tick_at.isoformat() if _last_tick_at else None,
            "next_run_at": next_run,
            "lock_held": _scrape_lock.locked(),
            "logs": list(_job_logs["scraping_tick"]),
        },
        {
            "id": "calendar_sync",
            "name": "Sync calendario La Liga",
            "type": "cron",
            "schedule": "Diario 06:00 UTC",
            "last_run_at": _last_calendar_sync_at.isoformat() if _last_calendar_sync_at else None,
            "next_run_at": next_calendar_sync,
            "logs": list(_job_logs["calendar_sync"]),
        },
        {
            "id": "deadline_check",
            "name": "Check deadline alineaciones",
            "type": "interval",
            "interval_seconds": 60,
            "last_run_at": _last_deadline_check_at.isoformat() if _last_deadline_check_at else None,
            "next_run_at": next_deadline_check,
            "logs": list(_job_logs["deadline_check"]),
        },
    ]

    return {
        # --- legacy flat fields (backward compatibility) ---
        "running": running,
        "poll_interval_seconds": scraping_settings.scraping_poll_interval_seconds,
        "last_tick_at": _last_tick_at.isoformat() if _last_tick_at else None,
        "next_run_at": next_run,
        "lock_held": _scrape_lock.locked(),
        "last_calendar_sync_at": _last_calendar_sync_at.isoformat()
        if _last_calendar_sync_at
        else None,
        "next_calendar_sync_at": next_calendar_sync,
        # --- new structured list ---
        "jobs": jobs,
    }


async def trigger_tick() -> dict:
    """Manually trigger a single scheduler tick.  Returns status."""
    if _scrape_lock.locked():
        return {"triggered": False, "reason": "previous tick still running"}

    _background_task = asyncio.create_task(_tick())  # noqa: RUF006
    return {"triggered": True}


async def trigger_calendar_sync() -> dict:
    """Manually trigger a calendar sync."""
    _background_task = asyncio.create_task(_calendar_sync())  # noqa: RUF006
    return {"triggered": True}


async def trigger_deadline_check() -> dict:
    """Manually trigger a deadline check."""
    _background_task = asyncio.create_task(_deadline_check())  # noqa: RUF006
    return {"triggered": True}
