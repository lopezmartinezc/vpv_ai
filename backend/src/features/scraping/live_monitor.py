"""Live match event monitor.

Polls futbolfantasy.com match pages during live games and sends
Telegram alerts when VPV-owned players score, get carded, etc.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.live_events import (
    EVENT_EMOJI,
    EVENT_LABEL,
    parse_live_events,
)
from src.features.scraping.log_buffer import scraping_log
from src.shared.models.matchday import Match
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.team import Team
from src.shared.models.user import User

logger = logging.getLogger(__name__)

_JOB_ID = "live_monitor"

# In-memory deduplication: match_id → set of (minute, event_type, player_slug)
_sent_events: dict[int, set[tuple[str, str, str]]] = {}
_last_run_at: datetime | None = None


async def live_match_monitor() -> None:
    """Scheduler job: check live matches for new events and send Telegram alerts."""
    global _last_run_at
    _last_run_at = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        try:
            await _check_live_matches(session)
        except Exception as exc:
            scraping_log(_JOB_ID, f"Error: {exc}", "error")
            logger.exception("live_match_monitor error")


async def _check_live_matches(session: AsyncSession) -> None:
    """Core logic: find live matches, parse events, send alerts."""
    from src.features.scraping.repository import ScrapingRepository

    repo = ScrapingRepository(session)
    season = await repo.get_active_season()
    if season is None:
        return

    # Check current + previous matchday (matches can overlap)
    matchday_numbers = [season.matchday_current]
    if season.matchday_current > 1:
        matchday_numbers.append(season.matchday_current - 1)

    now = datetime.now(UTC)
    live_matches: list[tuple[Match, int]] = []  # (match, matchday_number)

    for md_number in matchday_numbers:
        md = await repo.get_matchday(season.id, md_number)
        if md is None:
            continue
        matches = await repo.get_matches_for_matchday(md.id)
        for m in matches:
            if not m.source_url or not m.played_at:
                continue
            played_at = m.played_at
            if played_at.tzinfo is None:
                played_at = played_at.replace(tzinfo=UTC)
            # Match is "live" if started within last 3 hours
            elapsed = now - played_at
            if timedelta(minutes=-15) < elapsed < timedelta(hours=3):
                live_matches.append((m, md_number))

    if not live_matches:
        # Cleanup all sent events when no live matches
        _sent_events.clear()
        return

    scraping_log(
        _JOB_ID,
        f"{len(live_matches)} partidos en curso, comprobando eventos",
    )

    # Build player slug → (Player, owner_display_name) map for the season
    player_map = await _build_player_map(session, season.id)

    # Build team name map
    team_map = await _build_team_map(session, season.id)

    async with ScrapingClient() as client:
        for match, md_number in live_matches:
            try:
                html = await client.fetch(match.source_url)
            except ScrapingError:
                scraping_log(_JOB_ID, f"Error fetch match {match.id}", "warning")
                continue

            events = parse_live_events(html)
            if not events:
                continue

            home_team = team_map.get(match.home_team_id, "?")
            away_team = team_map.get(match.away_team_id, "?")

            # Get or create dedup set for this match
            is_first_scan = match.id not in _sent_events
            seen = _sent_events.setdefault(match.id, set())

            if is_first_scan:
                # First time seeing this match — mark all current events as seen
                # to avoid flooding with historical events
                for e in events:
                    seen.add(e.dedup_key)
                scraping_log(
                    _JOB_ID,
                    f"Match {match.id} ({home_team} vs {away_team}): "
                    f"primer scan, {len(events)} eventos marcados como vistos",
                )
                continue

            new_events = [e for e in events if e.dedup_key not in seen]
            if not new_events:
                continue
            score = (
                f"{match.home_score}-{match.away_score}" if match.home_score is not None else "vs"
            )

            for event in new_events:
                # Check if player belongs to a VPV participant
                info = player_map.get(event.player_slug)
                if info is None:
                    seen.add(event.dedup_key)  # not a VPV player, skip permanently
                    continue

                _player, owner_name = info
                if owner_name is None:
                    seen.add(event.dedup_key)  # no owner, skip permanently
                    continue

                # Format and send Telegram alert
                emoji = EVENT_EMOJI.get(event.event_type, "")
                label = EVENT_LABEL.get(event.event_type, event.event_type)
                msg = (
                    f"{emoji} <b>{label}</b> \u2014 {event.player_name} ({event.minute})\n"
                    f"{home_team} {score} {away_team} | J{md_number}\n"
                    f"Propietario: {owner_name}"
                )

                sent = await _send_telegram(session, msg)
                if sent:
                    seen.add(event.dedup_key)  # only mark sent on success
                    scraping_log(
                        _JOB_ID,
                        f"Enviado: {label} {event.player_name} ({event.minute}) -> {owner_name}",
                    )
                    await asyncio.sleep(1)  # rate limit: 1 msg/sec
                else:
                    scraping_log(
                        _JOB_ID,
                        f"FALLO envio: {label} {event.player_name} ({event.minute})",
                        "error",
                    )
                    # Will retry on next tick

    # Cleanup finished matches from dedup cache
    live_match_ids = {m.id for m, _ in live_matches}
    for mid in list(_sent_events.keys()):
        if mid not in live_match_ids:
            del _sent_events[mid]


async def _build_player_map(
    session: AsyncSession, season_id: int
) -> dict[str, tuple[Player, str | None]]:
    """Build slug → (Player, owner_display_name) for all players in the season."""
    stmt = (
        select(Player, User.display_name)
        .outerjoin(SeasonParticipant, Player.owner_id == SeasonParticipant.id)
        .outerjoin(User, SeasonParticipant.user_id == User.id)
        .where(Player.season_id == season_id)
    )
    result = await session.execute(stmt)
    mapping: dict[str, tuple[Player, str | None]] = {}
    for player, display_name in result.all():
        mapping[player.slug] = (player, display_name)
    return mapping


async def _build_team_map(session: AsyncSession, season_id: int) -> dict[int, str]:
    """Build team_id → short_name for teams in the season."""
    stmt = select(Team.id, Team.short_name, Team.name).where(Team.season_id == season_id)
    result = await session.execute(stmt)
    return {r.id: r.short_name or r.name for r in result.all()}


async def _send_telegram(session: AsyncSession, text: str) -> bool:
    """Send a Telegram alert. Returns True on success."""
    try:
        from src.features.telegram.service import TelegramNotifier

        notifier = TelegramNotifier(session)
        return await notifier.send_alert(text)
    except Exception as exc:
        scraping_log("live_monitor", f"Telegram error: {exc}", "error")
        return False


def get_live_monitor_status() -> dict:
    """Return status info for the admin dashboard."""
    return {
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
        "tracked_matches": len(_sent_events),
        "total_events_sent": sum(len(s) for s in _sent_events.values()),
    }
