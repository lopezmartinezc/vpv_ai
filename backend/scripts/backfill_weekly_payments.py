"""Backfill weekly_payment transactions for all scored matchdays.

Usage:
    cd backend && source .venv/bin/activate
    python -m scripts.backfill_weekly_payments [--season-id 8]
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.features.economy.service import EconomyService
from src.shared.models.matchday import Matchday

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def backfill(season_id: int) -> None:
    async with AsyncSessionLocal() as session:
        # Get all matchdays that are scored and count
        stmt = (
            select(Matchday.id, Matchday.number, Matchday.season_id)
            .where(
                Matchday.season_id == season_id,
                Matchday.stats_ok.is_(True),
                Matchday.counts.is_(True),
            )
            .order_by(Matchday.number.asc())
        )
        result = await session.execute(stmt)
        matchdays = result.all()

        logger.info("Found %d scored matchdays for season %d", len(matchdays), season_id)

        economy_svc = EconomyService(session)
        total_created = 0

        for md_id, md_number, s_id in matchdays:
            created = await economy_svc.generate_weekly_payments(s_id, md_id)
            if created > 0:
                logger.info("  J%d: created %d payments", md_number, created)
                total_created += created
            else:
                logger.info("  J%d: already has payments, skipped", md_number)

        await session.commit()
        logger.info("Done. Total transactions created: %d", total_created)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill weekly payments")
    parser.add_argument("--season-id", type=int, default=8, help="Season ID (default: 8)")
    args = parser.parse_args()
    asyncio.run(backfill(args.season_id))


if __name__ == "__main__":
    main()
