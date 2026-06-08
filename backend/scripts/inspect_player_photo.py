"""Diagnose what happens to alpha when we fetch a player's photo.

Picks a specific player by slug, fetches the futbolfantasy page,
extracts the photo URL, downloads it, inspects the source image, and
reports what would land on disk as WebP. Read-only — nothing in DB
or on disk is touched.

Usage::

    cd backend
    python -m scripts.inspect_player_photo <season_id> <slug>

Example::

    python -m scripts.inspect_player_photo 11 vinicius-junior
"""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import sys
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.core.logging import setup_logging
from src.features.scraping.client import ScrapingClient
from src.features.scraping.config import scraping_settings
from src.features.scraping.parsers import parse_player_photo
from src.shared.models.player import Player
from src.shared.models.season import Season

logger = logging.getLogger(__name__)


async def main(season_id: int, slug: str) -> None:
    setup_logging()

    async with AsyncSessionLocal() as session:
        player = (
            await session.execute(
                select(Player).where(Player.season_id == season_id, Player.slug == slug)
            )
        ).scalar_one_or_none()
        if player is None:
            print(f"Player not found: season={season_id} slug={slug}")
            sys.exit(1)

        season = await session.get(Season, season_id)
        url_suffix = f"/{season.scraping_slug}" if season and season.scraping_slug else ""

    base_url = scraping_settings.scraping_base_url
    primary_url = f"{base_url}/jugadores/{slug}{url_suffix}"
    print(f"Fetching {primary_url}")

    async with ScrapingClient() as client:
        try:
            html = await client.fetch(primary_url)
        except Exception as exc:
            print(f"Primary URL failed ({exc}), trying bare URL")
            html = await client.fetch(f"{base_url}/jugadores/{slug}")

        photo_url = parse_player_photo(html)
        if photo_url is None:
            print("No photo URL parsed from the page")
            sys.exit(1)
        print(f"Photo URL: {photo_url}")
        img_bytes = await client.fetch_bytes(photo_url)
        print(f"Source bytes: {len(img_bytes)}")

    src = Image.open(io.BytesIO(img_bytes))
    print(f"Source format: {src.format}")
    print(f"Source mode: {src.mode}")
    print(f"Source size: {src.size}")
    print(f"Source has alpha: {'A' in src.getbands()}")
    if src.mode == "P" and "transparency" in src.info:
        print("Source is palette-mode with transparency entry")

    # Show alpha histogram if present (to see if it's fully opaque,
    # fully transparent, or mixed).
    if "A" in src.getbands():
        alpha = src.split()[-1]
        hist = alpha.histogram()
        non_opaque_pixels = sum(hist[:255])
        opaque_pixels = hist[255]
        print(f"Alpha channel: opaque={opaque_pixels} non-opaque={non_opaque_pixels}")

    # Now apply the current pipeline (convert RGBA + resize) and check.
    converted = src.convert("RGBA")
    resized = converted.resize((200, 200), Image.Resampling.LANCZOS)
    if "A" in resized.getbands():
        alpha = resized.split()[-1]
        hist = alpha.histogram()
        print(f"After RGBA convert+resize: opaque={hist[255]} non-opaque={sum(hist[:255])}")

    # Save to memory and reopen as WebP to check what really gets written.
    buf = io.BytesIO()
    resized.save(buf, format="WEBP", quality=85)
    buf.seek(0)
    saved = Image.open(buf)
    print(f"Saved WebP mode: {saved.mode}")
    print(f"Saved WebP size: {saved.size}")
    print(f"Saved WebP has alpha: {'A' in saved.getbands()}")

    # Drop a temporary copy so the operator can eyeball it.
    out = Path("/tmp") / f"{slug}.inspect.webp"
    with open(out, "wb") as f:
        f.write(buf.getvalue())
    print(f"Wrote a copy for inspection: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("season_id", type=int)
    parser.add_argument("slug")
    args = parser.parse_args()
    asyncio.run(main(args.season_id, args.slug))
