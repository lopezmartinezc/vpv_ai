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
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.database import AsyncSessionLocal
from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.config import scraping_settings
from src.features.scraping.parsers import parse_match_crc, parse_match_score
from src.features.scraping.repository import ScrapingRepository
from src.features.scraping.service import ScrapingService

logger = logging.getLogger(__name__)

_scrape_lock = asyncio.Lock()
_scheduler: AsyncIOScheduler | None = None
_last_tick_at: datetime | None = None
_last_calendar_sync_at: datetime | None = None
_last_deadline_check_at: datetime | None = None

# ---------------------------------------------------------------------------
# Per-job log buffer (shared module to avoid circular imports)
# ---------------------------------------------------------------------------
from src.features.scraping.log_buffer import get_job_logs, scraping_log  # noqa: E402

_log = scraping_log


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
                    _log(
                        "scraping_tick",
                        f"Calendario: {cal_result['scores_updated']} resultados, {cal_result['dates_updated']} fechas",
                    )
                    await session.commit()
            except Exception as exc:
                _log("scraping_tick", f"Error calendario: {exc}", "error")

            # 3. Collect matchdays to check: current + previous (for late Marca/AS updates)
            matchdays_to_check: list[tuple[int, int]] = []  # (matchday_id, number)

            matchday = await repo.get_matchday(season_id, md_current)
            if matchday is not None:
                matchdays_to_check.append((matchday.id, md_current))

            if md_current > 1:
                prev_md = await repo.get_matchday(season_id, md_current - 1)
                if prev_md is not None:
                    matchdays_to_check.append((prev_md.id, md_current - 1))

            if not matchdays_to_check:
                _log("scraping_tick", f"Jornada {md_current} no encontrada")
                return

            # 4-5. Per-matchday CRC check + score discovery
            matches_to_scrape: list[tuple[int, int, int]] = []  # (match_id, md_id, md_number)
            pending_crcs: dict[int, str] = {}
            buffer_minutes = scraping_settings.scraping_buffer_minutes
            now_utc = datetime.now(UTC)

            async with ScrapingClient() as client:
                for md_id, md_number in matchdays_to_check:
                    matches = await repo.get_matches_for_matchday(md_id)
                    if not matches:
                        continue

                    played = [
                        m for m in matches if m.source_url is not None and m.home_score is not None
                    ]
                    pending_score = (
                        [
                            m
                            for m in matches
                            if m.source_url is not None
                            and m.home_score is None
                            and m.played_at is not None
                            and (now_utc - m.played_at) > timedelta(minutes=buffer_minutes)
                        ]
                        if md_number == md_current
                        else []
                    )  # only discover scores for current

                    if not played and not pending_score:
                        continue

                    _log(
                        "scraping_tick",
                        f"J{md_number}: {len(played)} con resultado, {len(pending_score)} pendientes",
                    )

                    # Score discovery (current matchday only)
                    for match in pending_score:
                        try:
                            html = await client.fetch(match.source_url)  # type: ignore[arg-type]
                        except ScrapingError:
                            _log("scraping_tick", f"Error fetch match id={match.id}", "warning")
                            continue

                        score = parse_match_score(html)
                        if score is None:
                            continue

                        home_score, away_score = score
                        _log(
                            "scraping_tick",
                            f"Match {match.id}: resultado descubierto {home_score}-{away_score}",
                        )
                        await repo.update_match_score(
                            match_id=match.id,
                            home_score=home_score,
                            away_score=away_score,
                            result=f"{home_score}-{away_score}",
                        )

                        new_crc = parse_match_crc(html)
                        if new_crc != match.stats_crc:
                            pending_crcs[match.id] = new_crc
                            matches_to_scrape.append((match.id, md_id, md_number))

                    # CRC check for played matches
                    for match in played:
                        try:
                            html = await client.fetch(match.source_url)  # type: ignore[arg-type]
                        except ScrapingError:
                            _log("scraping_tick", f"Error fetch match id={match.id}", "warning")
                            continue

                        new_crc = parse_match_crc(html)
                        if match.stats_crc == new_crc:
                            continue

                        _log(
                            "scraping_tick",
                            f"Match {match.id} (J{md_number}): CRC cambio {match.stats_crc} -> {new_crc}",
                        )
                        pending_crcs[match.id] = new_crc
                        matches_to_scrape.append((match.id, md_id, md_number))

                    # Force re-scrape for recently finished matches (player pages
                    # may update independently of the match page CRC).
                    rescrape_window = timedelta(hours=3)
                    already_queued = {m_id for m_id, _, _ in matches_to_scrape}
                    for match in played:
                        if match.id in already_queued:
                            continue
                        if not match.stats_ok or not match.played_at:
                            continue
                        played_at = match.played_at
                        if played_at.tzinfo is None:
                            played_at = played_at.replace(tzinfo=UTC)
                        elapsed = now_utc - played_at
                        if elapsed < rescrape_window:
                            _log(
                                "scraping_tick",
                                f"Match {match.id} (J{md_number}): re-scrape forzado "
                                f"({int(elapsed.total_seconds() // 60)} min desde inicio)",
                            )
                            matches_to_scrape.append((match.id, md_id, md_number))

            if not matches_to_scrape:
                _log("scraping_tick", "CRCs sin cambios, nada que scrapear")
                await session.commit()
                return

            # 6. Scrape changed matches
            _log(
                "scraping_tick",
                f"Scrapeando {len(matches_to_scrape)} partidos",
            )
            for match_id, _md_id, md_number in matches_to_scrape:
                try:
                    result = await service.scrape_match_players(
                        season_id,
                        md_number,
                        match_id,
                    )
                    processed = result.get("processed", 0)
                    _log(
                        "scraping_tick",
                        f"Match {match_id} (J{md_number}): procesados={processed}, errores={result.get('errors', 0)}",
                    )
                    if processed and match_id in pending_crcs:
                        await repo.update_match_crc(match_id, pending_crcs[match_id])
                    elif not processed and match_id in pending_crcs:
                        _log(
                            "scraping_tick",
                            f"Match {match_id}: sin stats, CRC NO actualizado — se reintentará",
                        )
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

# ---------------------------------------------------------------------------
# Deadline reminder tracking
# ---------------------------------------------------------------------------
_reminders_sent: dict[int, set[str]] = {}  # matchday_number → set of "2h"/"30min"
_last_deadline_reminder_at: datetime | None = None

_REMINDER_WINDOWS = [
    ("2h", 120),  # label, minutes before deadline
    ("30min", 30),
    ("15min", 15),
]


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
                deadline = matchday.first_match_at - timedelta(minutes=season.lineup_deadline_min)

            if deadline is None:
                return

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
# Deadline reminder (Telegram notifications before deadline)
# ---------------------------------------------------------------------------


async def _deadline_reminder() -> None:
    """Send Telegram reminders at 2h and 30min before lineup deadline."""
    global _last_deadline_reminder_at
    _last_deadline_reminder_at = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        try:
            from src.features.lineups.repository import LineupRepository
            from src.shared.models.user import User

            scraping_repo = ScrapingRepository(session)
            lineup_repo = LineupRepository(session)

            season = await scraping_repo.get_active_season()
            if season is None:
                return

            md_number = season.matchday_current
            if md_number == 0:
                return

            matchday = await lineup_repo.get_matchday(season.id, md_number)
            if matchday is None:
                return

            # Compute deadline
            deadline = matchday.deadline_at
            if deadline is None and matchday.first_match_at is not None:
                deadline = matchday.first_match_at - timedelta(minutes=season.lineup_deadline_min)

            if deadline is None:
                return

            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)

            now = datetime.now(UTC)
            if now >= deadline:
                return  # Deadline already passed

            minutes_left = (deadline - now).total_seconds() / 60
            sent_for_md = _reminders_sent.get(md_number, set())

            for label, window_minutes in _REMINDER_WINDOWS:
                if label in sent_for_md:
                    continue
                # Fire once when we cross the window threshold
                if minutes_left > window_minutes or minutes_left < window_minutes - 5:
                    continue

                # Get participants without lineup
                missing = await lineup_repo.get_participants_without_lineup(season.id, matchday.id)
                if not missing:
                    _log("deadline_reminder", f"J{md_number} ({label}): todos han enviado")
                    sent_for_md.add(label)
                    _reminders_sent[md_number] = sent_for_md
                    continue

                # Get display names
                from sqlalchemy import select as sa_select

                user_ids = [p.user_id for p in missing]
                stmt = sa_select(User.id, User.display_name).where(User.id.in_(user_ids))
                result = await session.execute(stmt)
                user_names = {row.id: row.display_name for row in result.all()}

                names = [user_names.get(p.user_id, "?") for p in missing]
                names_str = ", ".join(names)

                if window_minutes >= 60:
                    time_str = f"{window_minutes // 60}h"
                else:
                    time_str = f"{window_minutes}min"

                message = (
                    f"\u23f0 Faltan {time_str} para el deadline de J{md_number}\n"
                    f"Sin alineacion: {names_str}"
                )

                # Send to Telegram group
                from src.features.telegram.service import TelegramNotifier

                notifier = TelegramNotifier(session)
                await notifier.send_alert(message)

                # Send push notifications to users without lineup
                try:
                    from src.features.notifications.service import NotificationService

                    push_service = NotificationService(session)
                    push_user_ids = [p.user_id for p in missing]
                    md_url = f"/jornadas/{md_number}/alineacion"
                    push_sent = await push_service.send_push_to_users(
                        user_ids=push_user_ids,
                        title=f"Deadline J{md_number}",
                        body=f"Faltan {time_str} para enviar alineacion",
                        url=md_url,
                    )
                    if push_sent:
                        _log("deadline_reminder", f"Push: {push_sent} notificaciones enviadas")
                except Exception as push_exc:
                    _log("deadline_reminder", f"Push error: {push_exc}", "warning")

                sent_for_md.add(label)
                _reminders_sent[md_number] = sent_for_md
                _log(
                    "deadline_reminder",
                    f"J{md_number} ({label}): aviso enviado — {len(missing)} sin alineacion",
                )

                # Clean old matchday entries
                for old_md in list(_reminders_sent.keys()):
                    if old_md < md_number:
                        del _reminders_sent[old_md]

        except Exception as exc:
            _log("deadline_reminder", f"Error: {exc}", "error")


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
            _log(
                "calendar_sync",
                f"Completado: {result['scores_updated']} resultados, {result['dates_updated']} fechas actualizadas",
            )

        except Exception as exc:
            await session.rollback()
            _log("calendar_sync", f"Error: {exc}", "error")


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


def start_scheduler(**_kwargs: object) -> None:
    """Create and start the AsyncIOScheduler.  Idempotent.

    IMPORTANT: uvicorn must run with --workers 1 to avoid duplicate schedulers.
    """
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
    _scheduler.add_job(
        _deadline_reminder,
        trigger="interval",
        seconds=60,
        id="deadline_reminder",
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=30,
    )
    if scraping_settings.live_monitor_enabled:
        from src.features.scraping.live_monitor import live_match_monitor

        live_interval = scraping_settings.live_monitor_interval_seconds
        _scheduler.add_job(
            live_match_monitor,
            trigger="interval",
            seconds=live_interval,
            id="live_monitor",
            max_instances=1,
            replace_existing=True,
            misfire_grace_time=30,
        )
    _scheduler.start()
    logger.info(
        "scheduler.start: started, tick_interval=%ds, calendar_sync=daily@06:00, deadline_check=60s, live_monitor=%ds",
        interval,
        scraping_settings.live_monitor_interval_seconds,
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
    next_deadline_reminder = _next("deadline_reminder")

    try:
        from src.features.scraping.live_monitor import get_live_monitor_status

        _live_status = get_live_monitor_status()
        _live_last_run = _live_status["last_run_at"]
    except Exception:
        _live_last_run = None

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
            "logs": get_job_logs("scraping_tick"),
        },
        {
            "id": "calendar_sync",
            "name": "Sync calendario La Liga",
            "type": "cron",
            "schedule": "Diario 06:00 UTC",
            "last_run_at": _last_calendar_sync_at.isoformat() if _last_calendar_sync_at else None,
            "next_run_at": next_calendar_sync,
            "logs": get_job_logs("calendar_sync"),
        },
        {
            "id": "deadline_check",
            "name": "Check deadline alineaciones",
            "type": "interval",
            "interval_seconds": 60,
            "last_run_at": _last_deadline_check_at.isoformat()
            if _last_deadline_check_at
            else None,
            "next_run_at": next_deadline_check,
            "logs": get_job_logs("deadline_check"),
        },
        {
            "id": "deadline_reminder",
            "name": "Recordatorio deadline (Telegram)",
            "type": "interval",
            "interval_seconds": 60,
            "last_run_at": _last_deadline_reminder_at.isoformat()
            if _last_deadline_reminder_at
            else None,
            "next_run_at": next_deadline_reminder,
            "logs": get_job_logs("deadline_reminder"),
        },
        {
            "id": "manual_scrape",
            "name": "Scraping manual (admin)",
            "type": "manual",
            "logs": get_job_logs("manual_scrape"),
        },
        {
            "id": "live_monitor",
            "name": "Monitor en directo (Telegram)",
            "type": "interval",
            "interval_seconds": scraping_settings.live_monitor_interval_seconds,
            "last_run_at": _live_last_run,
            "next_run_at": _next("live_monitor"),
            "logs": get_job_logs("live_monitor"),
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
