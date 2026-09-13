"""Live match event monitor.

Polls futbolfantasy.com match pages during live games and sends
Telegram alerts when VPV-owned players score, get carded, etc.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.live_events import (
    EVENT_EMOJI,
    EVENT_LABEL,
    LiveEvent,
    parse_live_events,
)
from src.features.scraping.log_buffer import scraping_log
from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.team import Team
from src.shared.models.user import User

logger = logging.getLogger(__name__)

_JOB_ID = "live_monitor"

BURGER = "\U0001f354"  # 🍔

# In-memory deduplication: match_id → set of (minute, event_type, player_slug)
_sent_events: dict[int, set[tuple[str, str, str]]] = {}
_last_run_at: datetime | None = None


def is_burger_goal(
    event_type: str,
    player: Player | None,
    matchday_counts: bool,
    match_counts: bool,
    lined_up: set[tuple[int, int]],
) -> bool:
    """Whether a goal is a 🍔: its scorer belongs to someone who left him out.

    The same rule as the burger ranking (``burger_ranking/service.py``): the
    player is owned, his owner did not field him in that matchday's eleven —
    no lineup at all included — and both the matchday and the fixture count.
    ``lined_up`` holds the (participant_id, player_id) pairs of that matchday.
    """
    if event_type != "goal" or player is None or player.owner_id is None:
        return False
    if not (matchday_counts and match_counts):
        return False
    return (player.owner_id, player.id) not in lined_up


def format_live_alert(
    event: LiveEvent,
    *,
    home_team: str,
    away_team: str,
    score: str,
    matchday_number: int,
    owner_name: str | None,
    burger: bool = False,
) -> str:
    """The Telegram message for one live event (HTML parse mode)."""
    emoji = EVENT_EMOJI.get(event.event_type, "") + (BURGER if burger else "")
    label = EVENT_LABEL.get(event.event_type, event.event_type)
    owner_line = ""
    if owner_name is not None:
        owner_line = f"\nPropietario: {escape(owner_name)}"
        if burger:
            owner_line += f" — {BURGER} no estaba en su once"
    return (
        f"{emoji} <b>{label}</b> — {escape(event.player_name)} ({event.minute})\n"
        f"{escape(home_team)} {score} {escape(away_team)} | J{matchday_number}"
        f"{owner_line}"
    )


async def live_match_monitor() -> None:
    """Scheduler job: check live matches for new events and send Telegram alerts."""
    global _last_run_at
    _last_run_at = datetime.now(UTC)

    try:
        async with AsyncSessionLocal() as session:
            await _check_live_matches(session)
    except Exception as exc:
        # Catch ALL exceptions to prevent APScheduler from killing the job
        scraping_log(_JOB_ID, f"Error fatal: {exc}", "error")
        logger.exception("live_match_monitor error")


async def _check_live_matches(session: AsyncSession) -> None:
    """Core logic: find live matches, parse events, send alerts."""
    from src.features.scraping.repository import ScrapingRepository

    repo = ScrapingRepository(session)
    season = await repo.get_active_season()
    if season is None:
        return

    now = datetime.now(UTC)
    # (match, matchday_number, matchday_counts)
    live_matches: list[tuple[Match, int, bool]] = []

    # Find ALL live matches across any matchday (not just current)
    # by querying matches with played_at in the live window
    live_window_start = now - timedelta(hours=3)
    live_window_end = now + timedelta(minutes=15)

    stmt = (
        select(Match, Matchday.number, Matchday.counts)
        .join(Matchday, Match.matchday_id == Matchday.id)
        .where(
            Matchday.season_id == season.id,
            Match.source_url.isnot(None),
            Match.played_at.isnot(None),
            Match.played_at > live_window_start,
            Match.played_at < live_window_end,
        )
    )
    result = await session.execute(stmt)
    for match, md_number, md_counts in result.all():
        live_matches.append((match, md_number, md_counts))

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

    # Who fielded whom in the matchdays being played, to tell a 🍔 goal
    lined_up = await _lined_up_by_matchday(session, {m.matchday_id for m, _, _ in live_matches})

    async with ScrapingClient() as client:
        for match, md_number, md_counts in live_matches:
            try:
                html = await client.fetch(match.source_url)  # type: ignore[arg-type]
            except ScrapingError:
                scraping_log(_JOB_ID, f"Error fetch match {match.id}", "warning")
                continue

            events = parse_live_events(html)
            if not events:
                continue

            home_team = team_map.get(match.home_team_id, "?")
            away_team = team_map.get(match.away_team_id, "?")

            # Events that always send (regardless of VPV ownership)
            always_send = {"goal"}

            # Get or create dedup set for this match
            is_first_scan = match.id not in _sent_events
            seen = _sent_events.setdefault(match.id, set())

            if is_first_scan:
                # First time seeing this match — mark all current events as seen
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

            sends_this_tick = 0

            from src.features.telegram.alerts_config import is_live_event_enabled

            for event in new_events:
                info = player_map.get(event.player_slug)
                player, owner_name = info if info else (None, None)

                is_vpv = owner_name is not None
                if not is_vpv and event.event_type not in always_send:
                    seen.add(event.dedup_key)
                    continue

                # Per-subtype opt-out: admin disabled this event type
                # for the season. Mark as seen so we don't re-evaluate
                # it on every tick.
                if not is_live_event_enabled(season.alerts_config, event.event_type):
                    seen.add(event.dedup_key)
                    continue

                label = EVENT_LABEL.get(event.event_type, event.event_type)
                burger = is_burger_goal(
                    event.event_type,
                    player,
                    md_counts,
                    match.counts,
                    lined_up.get(match.matchday_id, set()),
                )
                msg = format_live_alert(
                    event,
                    home_team=home_team,
                    away_team=away_team,
                    score=score,
                    matchday_number=md_number,
                    owner_name=owner_name,
                    burger=burger,
                )

                sent = await _send_telegram(session, msg, season_id=season.id)
                if sent:
                    seen.add(event.dedup_key)  # only mark sent on success
                    sends_this_tick += 1
                    scraping_log(
                        _JOB_ID,
                        f"Enviado: {label} {event.player_name} ({event.minute}) -> {owner_name}"
                        f"{' (hamburguesa)' if burger else ''}",
                    )
                    if sends_this_tick >= 5:
                        break  # max 5 per tick, rest will be sent next tick
                    await asyncio.sleep(1.5)  # rate limit
                else:
                    scraping_log(
                        _JOB_ID,
                        f"FALLO envio: {label} {event.player_name} ({event.minute})",
                        "error",
                    )
                    # Will retry on next tick

    # Cleanup finished matches from dedup cache
    live_match_ids = {m.id for m, _, _ in live_matches}
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


async def _lined_up_by_matchday(
    session: AsyncSession, matchday_ids: set[int]
) -> dict[int, set[tuple[int, int]]]:
    """matchday_id → the (participant_id, player_id) pairs in its lineups."""
    if not matchday_ids:
        return {}
    stmt = (
        select(Lineup.matchday_id, Lineup.participant_id, LineupPlayer.player_id)
        .join(LineupPlayer, LineupPlayer.lineup_id == Lineup.id)
        .where(Lineup.matchday_id.in_(matchday_ids))
    )
    result = await session.execute(stmt)
    fielded: dict[int, set[tuple[int, int]]] = {}
    for matchday_id, participant_id, player_id in result.all():
        fielded.setdefault(matchday_id, set()).add((participant_id, player_id))
    return fielded


async def _build_team_map(session: AsyncSession, season_id: int) -> dict[int, str]:
    """Build team_id → short_name for teams in the season."""
    stmt = select(Team.id, Team.short_name, Team.name).where(Team.season_id == season_id)
    result = await session.execute(stmt)
    return {r.id: r.short_name or r.name for r in result.all()}


async def _send_telegram(session: AsyncSession, text: str, season_id: int | None = None) -> bool:
    """Send a Telegram alert. Returns True on success.

    Uses the same per-season alerts resolution as ``TelegramNotifier.send_alert``
    so Mundial events land in the Mundial chat instead of leaking to the
    global Liga channel.
    """
    try:
        from src.features.telegram.client import TelegramClient
        from src.features.telegram.config import telegram_settings
        from src.features.telegram.service import resolve_alerts_target

        if not telegram_settings.telegram_enabled:
            scraping_log("live_monitor", "Telegram desactivado", "warning")
            return False

        chat_id, thread_id = await resolve_alerts_target(session, season_id)

        async with TelegramClient() as client:
            result = await client.send_message(
                chat_id=chat_id, text=text, message_thread_id=thread_id
            )

        if result.get("ok"):
            return True

        error_desc = result.get("description", "unknown error")
        scraping_log("live_monitor", f"Telegram API error: {error_desc}", "error")
        return False
    except Exception as exc:
        scraping_log("live_monitor", f"Telegram exception: {exc}", "error")
        return False


def get_live_monitor_status() -> dict:
    """Return status info for the admin dashboard."""
    return {
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
        "tracked_matches": len(_sent_events),
        "total_events_sent": sum(len(s) for s in _sent_events.values()),
    }
