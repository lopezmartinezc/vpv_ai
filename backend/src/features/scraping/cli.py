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

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.logging import setup_logging
from src.features.scraping.service import ScrapingService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_with_session(coro_factory) -> None:  # type: ignore[type-arg]
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


async def cmd_scrape_match(
    season_id: int, matchday_number: int, match_id: int
) -> None:
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
    """Update La Liga match scores from the calendar page."""

    async def _run(session: AsyncSession) -> dict:
        service = ScrapingService(session)
        count = await service.scrape_calendar(season_id)
        return {"matches_updated": count}

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
    p_matchday = sub.add_parser(
        "scrape-matchday", help="Scrape all player stats for a matchday"
    )
    p_matchday.add_argument("season_id", type=int, help="Season primary-key ID")
    p_matchday.add_argument("matchday_number", type=int, help="Matchday number (1-38)")

    # scrape-match
    p_match = sub.add_parser(
        "scrape-match", help="Scrape stats for a single match"
    )
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

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
