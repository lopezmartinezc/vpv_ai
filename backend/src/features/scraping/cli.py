"""CLI entry point for scraping commands.

Usage::

    python -m src.features.scraping.cli scrape-matchday <season_id> <matchday_number>
    python -m src.features.scraping.cli scrape-match <season_id> <matchday_number> <match_id>
    python -m src.features.scraping.cli check-updates
    python -m src.features.scraping.cli update-calendar <season_id>
    python -m src.features.scraping.cli scrape-current

Each command opens its own ``AsyncSession``, calls the appropriate
``ScrapingService`` method, commits on success and rolls back on failure.
Results are printed to stdout as JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.logging import setup_logging
from src.features.scraping.service import ScrapingService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_with_session(coro_factory: Any) -> None:
    """Execute *coro_factory(session)* inside a managed session.

    Commits on success, rolls back on exception, and always closes the
    session.  The coroutine's return value is printed as JSON.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await coro_factory(session)
            await session.commit()
            print(json.dumps(result, indent=2))
        except Exception as exc:
            await session.rollback()
            logger.error("CLI command failed: %s", exc, exc_info=True)
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


async def cmd_scrape_matchday(season_id: int, matchday_number: int) -> None:
    """Scrape all player stats for *matchday_number* in *season_id*."""

    async def _run(session: AsyncSession) -> dict:
        service = ScrapingService(session)
        return await service.scrape_matchday(season_id, matchday_number)

    await _run_with_session(_run)


async def cmd_scrape_match(season_id: int, matchday_number: int, match_id: int) -> None:
    """Scrape player stats for a single *match_id* in *matchday_number*."""

    async def _run(session: AsyncSession) -> dict:
        service = ScrapingService(session)
        return await service.scrape_match_players(season_id, matchday_number, match_id)

    await _run_with_session(_run)


async def cmd_check_updates() -> None:
    """Check the futbolfantasy homepage for CRC changes."""

    async def _run(session: AsyncSession) -> dict:
        service = ScrapingService(session)
        match_ids = await service.check_for_updates()
        return {"changed": len(match_ids) > 0, "ready_match_ids": match_ids}

    await _run_with_session(_run)


async def cmd_update_calendar(season_id: int) -> None:
    """Update La Liga match scores and dates from the calendar page."""

    async def _run(session: AsyncSession) -> dict:
        service = ScrapingService(session)
        return await service.scrape_calendar(season_id)

    await _run_with_session(_run)


async def cmd_refresh_positions(season_id: int, concurrency: int) -> None:
    """Re-check every active player's VPV position (fast, no photo download)."""

    async def _run(session: AsyncSession) -> dict:
        from src.features.scraping.photos import PhotoDownloader

        downloader = PhotoDownloader(session)
        return await downloader.refresh_positions(season_id, concurrency=concurrency)

    await _run_with_session(_run)


async def cmd_download_photos(
    season_id: int, refresh: bool, force_redownload: bool, photos_only: bool
) -> None:
    """Download player photos for *season_id* (optionally refresh positions)."""

    async def _run(session: AsyncSession) -> dict:
        from src.features.scraping.photos import PhotoDownloader

        downloader = PhotoDownloader(session)
        return await downloader.download_all(
            season_id,
            refresh=refresh,
            force_redownload=force_redownload,
            photos_only=photos_only,
        )

    await _run_with_session(_run)


async def cmd_scrape_season_full(season_id: int, start: int | None, end: int | None) -> None:
    """Re-scrape *season_id* by iterating players (1 HTTP fetch per player).

    Use for season-wide audits: ~N times fewer requests than looping
    ``scrape-matchday`` over every matchday.
    """

    async def _run(session: AsyncSession) -> dict:
        service = ScrapingService(session)
        return await service.scrape_season_by_player(season_id, start=start, end=end)

    await _run_with_session(_run)


async def cmd_import_rosters(season_id: int) -> None:
    """Fetch every existing team's roster page and create missing players.

    Use when the initial ``initialize`` of a season created the team rows but
    failed to populate ``players`` (typical when the parser was broken). Safe
    to re-run: existing slugs are skipped via ``uq_player_slug``.
    """

    async def _run(session: AsyncSession) -> dict:
        service = ScrapingService(session)
        return await service.import_rosters_only(season_id)

    await _run_with_session(_run)


async def cmd_sync_rosters(season_id: int) -> None:
    """Reconcile every team's roster with the live source.

    Adds new players, reactivates returning ones, and soft-deletes (flips
    ``is_available=False``) those no longer on the official squad. Safer than
    a hard DELETE: lineups and draft picks that referenced the dropped
    players keep working but the search/predictions UI stops offering them.
    """

    async def _run(session: AsyncSession) -> dict:
        service = ScrapingService(session)
        return await service.sync_rosters(season_id)

    await _run_with_session(_run)


async def cmd_scrape_current() -> None:
    """Scrape the current matchday for the active season.

    Reads ``season.matchday_current`` from the active season and delegates to
    ``scrape_matchday``.  Exits with an error if no active season is found.
    """

    async def _run(session: AsyncSession) -> dict:
        from src.features.scraping.repository import ScrapingRepository

        repo = ScrapingRepository(session)
        season = await repo.get_active_season()
        if season is None:
            raise RuntimeError("No active season found in the database.")
        logger.info(
            "scrape-current: season_id=%d matchday_current=%d",
            season.id,
            season.matchday_current,
        )
        service = ScrapingService(session)
        return await service.scrape_matchday(season.id, season.matchday_current)

    await _run_with_session(_run)


async def cmd_simulate_live(season_id: int, urls: list[str]) -> dict[str, Any]:
    """Dry-run the live-match alert pipeline against given match URLs.

    Fetches every URL, parses live events the same way ``live_monitor``
    does, then walks each event through the SAME filters that would
    decide whether to send a Telegram message: ownership (always-send
    list) and ``alerts_config`` per-subtype gate. Nothing is sent.

    Prints, per URL:
    - parsed events count
    - which events WOULD send (with the rendered Telegram text)
    - which events were FILTERED OUT and why

    The dedup map is intentionally ignored — the simulation is for
    config validation, not for replaying historical reality.
    """
    from src.features.scraping.client import ScrapingClient
    from src.features.scraping.live_events import (
        EVENT_EMOJI,
        EVENT_LABEL,
        parse_live_events,
    )
    from src.features.telegram.alerts_config import is_live_event_enabled

    async def _run(session: AsyncSession) -> dict[str, Any]:
        from sqlalchemy import select

        from src.shared.models.season import Season

        season = await session.get(Season, season_id)
        if season is None:
            return {"error": f"season_id={season_id} not found"}

        # Build the ownership map (slug → owner display_name) for the
        # season so we can respect the always-send vs VPV-only rule.
        from src.shared.models.participant import SeasonParticipant
        from src.shared.models.player import Player
        from src.shared.models.user import User

        stmt = (
            select(Player.slug, User.display_name)
            .outerjoin(SeasonParticipant, Player.owner_id == SeasonParticipant.id)
            .outerjoin(User, SeasonParticipant.user_id == User.id)
            .where(Player.season_id == season_id)
        )
        result = await session.execute(stmt)
        ownership: dict[str, str | None] = {row.slug: row.display_name for row in result.all()}

        always_send = {"goal"}
        per_url: list[dict[str, Any]] = []

        async with ScrapingClient() as client:
            for url in urls:
                try:
                    html = await client.fetch(url)
                except Exception as exc:
                    per_url.append({"url": url, "error": f"fetch failed: {exc}"})
                    continue

                events = parse_live_events(html)
                would_send: list[dict[str, Any]] = []
                filtered: list[dict[str, Any]] = []

                for event in events:
                    owner_name = ownership.get(event.player_slug)
                    is_vpv = owner_name is not None
                    if not is_vpv and event.event_type not in always_send:
                        filtered.append(
                            {
                                "event_type": event.event_type,
                                "player": event.player_name,
                                "minute": event.minute,
                                "reason": "not VPV (and not in always_send list)",
                            }
                        )
                        continue
                    if not is_live_event_enabled(season.alerts_config, event.event_type):
                        filtered.append(
                            {
                                "event_type": event.event_type,
                                "player": event.player_name,
                                "minute": event.minute,
                                "reason": (
                                    "disabled in alerts_config "
                                    f"(live_match.{event.event_type}=false)"
                                ),
                            }
                        )
                        continue

                    emoji = EVENT_EMOJI.get(event.event_type, "")
                    label = EVENT_LABEL.get(event.event_type, event.event_type)
                    rendered = f"{emoji} {label} — {event.player_name} ({event.minute})" + (
                        f" | Propietario: {owner_name}" if is_vpv else ""
                    )
                    would_send.append(
                        {
                            "event_type": event.event_type,
                            "player": event.player_name,
                            "minute": event.minute,
                            "vpv_owner": owner_name,
                            "rendered": rendered,
                        }
                    )

                per_url.append(
                    {
                        "url": url,
                        "events_parsed": len(events),
                        "would_send": would_send,
                        "filtered": filtered,
                    }
                )

        # Top-line summary so the operator can eyeball the result.
        total_send = sum(len(b["would_send"]) for b in per_url if "would_send" in b)
        total_filtered = sum(len(b["filtered"]) for b in per_url if "filtered" in b)
        return {
            "season_id": season_id,
            "season_name": season.name,
            "alerts_config": season.alerts_config,
            "summary": {
                "matches": len(urls),
                "would_send_total": total_send,
                "filtered_total": total_filtered,
            },
            "matches": per_url,
        }

    return await _run_simulate_and_print(_run)


async def _run_simulate_and_print(coro_factory: Any) -> dict[str, Any]:
    """Variant of _run_with_session that returns the dict for simulate-live."""
    async with AsyncSessionLocal() as session:
        try:
            result = await coro_factory(session)
            # Rollback by default — simulation must never persist anything.
            await session.rollback()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return result
        except Exception as exc:
            await session.rollback()
            logger.error("simulate-live failed: %s", exc, exc_info=True)
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.features.scraping.cli",
        description="VPV Fantasy scraping CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scrape-matchday
    p_matchday = sub.add_parser("scrape-matchday", help="Scrape all player stats for a matchday")
    p_matchday.add_argument("season_id", type=int, help="Season primary-key ID")
    p_matchday.add_argument("matchday_number", type=int, help="Matchday number (1-38)")

    # scrape-match
    p_match = sub.add_parser("scrape-match", help="Scrape stats for a single match")
    p_match.add_argument("season_id", type=int, help="Season primary-key ID")
    p_match.add_argument("matchday_number", type=int, help="Matchday number (1-38)")
    p_match.add_argument("match_id", type=int, help="Match primary-key ID")

    # check-updates
    sub.add_parser("check-updates", help="Check homepage CRC for new stats")

    # update-calendar
    p_calendar = sub.add_parser(
        "update-calendar", help="Update match scores from La Liga calendar"
    )
    p_calendar.add_argument("season_id", type=int, help="Season primary-key ID")

    # scrape-current
    sub.add_parser(
        "scrape-current",
        help="Scrape current matchday for the active season",
    )

    # scrape-season-full
    p_full = sub.add_parser(
        "scrape-season-full",
        help="Re-scrape a whole season by iterating players (1 fetch each)",
    )
    p_full.add_argument("season_id", type=int, help="Season primary-key ID")
    p_full.add_argument(
        "--start", type=int, default=None, help="First matchday number (inclusive)"
    )
    p_full.add_argument("--end", type=int, default=None, help="Last matchday number (inclusive)")

    # simulate-live
    p_sim = sub.add_parser(
        "simulate-live",
        help=(
            "Dry-run the live-event Telegram pipeline against given "
            "match URLs. Honors the season's alerts_config so you can "
            "verify which subtypes would actually be sent. Nothing is "
            "persisted, nothing is sent to Telegram."
        ),
    )
    p_sim.add_argument("season_id", type=int, help="Season primary-key ID")
    p_sim.add_argument(
        "urls",
        nargs="+",
        help="Match URL(s) on futbolfantasy.com (e.g. https://.../partidos/12345-...)",
    )

    # refresh-positions
    p_refpos = sub.add_parser(
        "refresh-positions",
        help=(
            "Re-check every active player's VPV position (POR/DEF/MED/DEL) "
            "in parallel. Skips the photo download/Pillow step so a full "
            "Mundial squad finishes in ~10-15 min instead of ~70."
        ),
    )
    p_refpos.add_argument("season_id", type=int, help="Season primary-key ID")
    p_refpos.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max parallel HTTP fetches (default: 5)",
    )

    # download-photos
    p_photos = sub.add_parser(
        "download-photos",
        help=(
            "Download player photos as WebP. Pass --refresh to re-fetch "
            "every active player and update their VPV position when it "
            "changed in the source (mid-tournament reclassifications)."
        ),
    )
    p_photos.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Process every available player (not only those missing "
            "photo/position) and update positions that differ from the "
            "source. Does NOT re-download photos that are already on "
            "disk — use --force-redownload for that."
        ),
    )
    p_photos.add_argument(
        "--force-redownload",
        action="store_true",
        help=(
            "Delete every existing WebP from disk + clear photo_path in "
            "the DB before the download runs, forcing every player to "
            "be fetched again from futbolfantasy. Use after a source "
            "change or to undo a bad batch (e.g. all photos saved with "
            "the wrong background)."
        ),
    )
    p_photos.add_argument(
        "--photos-only",
        action="store_true",
        help=(
            "Photos-only mode: process every active player in the season "
            "and force re-download of their photo, but NEVER touch their "
            "stored position. Equivalent to --refresh --force-redownload "
            "minus position writes. Use when you want fresh artwork "
            "without risking position regressions on a season whose "
            "positions are already correct (e.g. World Cup squad photos "
            "after the tournament closes)."
        ),
    )
    p_photos.add_argument("season_id", type=int, help="Season primary-key ID")

    # import-rosters
    p_rosters = sub.add_parser(
        "import-rosters",
        help="Fetch each team's roster and create missing players (idempotent)",
    )
    p_rosters.add_argument("season_id", type=int, help="Season primary-key ID")

    # sync-rosters
    p_sync = sub.add_parser(
        "sync-rosters",
        help=(
            "Reconcile each team's roster with the live source — adds new "
            "players, reactivates returning ones, soft-deletes those cut "
            "from the squad."
        ),
    )
    p_sync.add_argument("season_id", type=int, help="Season primary-key ID")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate async command."""
    setup_logging()
    # Ensure standard-library loggers used by the scraping package are visible.
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    parser = _build_parser()
    args = parser.parse_args()

    command = args.command

    if command == "scrape-matchday":
        asyncio.run(cmd_scrape_matchday(args.season_id, args.matchday_number))

    elif command == "scrape-match":
        asyncio.run(cmd_scrape_match(args.season_id, args.matchday_number, args.match_id))

    elif command == "check-updates":
        asyncio.run(cmd_check_updates())

    elif command == "update-calendar":
        asyncio.run(cmd_update_calendar(args.season_id))

    elif command == "scrape-current":
        asyncio.run(cmd_scrape_current())

    elif command == "scrape-season-full":
        asyncio.run(cmd_scrape_season_full(args.season_id, args.start, args.end))

    elif command == "import-rosters":
        asyncio.run(cmd_import_rosters(args.season_id))

    elif command == "sync-rosters":
        asyncio.run(cmd_sync_rosters(args.season_id))

    elif command == "download-photos":
        asyncio.run(
            cmd_download_photos(
                args.season_id,
                args.refresh,
                args.force_redownload,
                args.photos_only,
            )
        )

    elif command == "refresh-positions":
        asyncio.run(cmd_refresh_positions(args.season_id, args.concurrency))

    elif command == "simulate-live":
        asyncio.run(cmd_simulate_live(args.season_id, args.urls))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
