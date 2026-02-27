"""Download and process player photos from futbolfantasy.com.

Photos are fetched from the player's profile page, resized to 200x200,
converted to WebP, and stored under ``static/players/{slug}.webp``.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.config import scraping_settings
from src.features.scraping.parsers import parse_player_photo
from src.features.scraping.repository import ScrapingRepository

logger = logging.getLogger(__name__)

# Output directory — resolved relative to the backend project root.
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_PHOTOS_DIR = _BACKEND_ROOT / "static" / "players"

PHOTO_SIZE = (200, 200)
WEBP_QUALITY = 85


class PhotoDownloader:
    """Download, convert, and persist player photos."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ScrapingRepository(session)
        self._settings = scraping_settings

    async def download_all(self, season_id: int) -> dict[str, int]:
        """Download photos for every player in *season_id* that lacks one.

        Returns a summary dict with keys ``downloaded``, ``skipped``, ``errors``.
        """
        _PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

        players = await self.repo.get_players_without_photo(season_id)
        logger.info("PhotoDownloader: %d players without photo", len(players))

        downloaded = 0
        skipped = 0
        errors = 0

        base_url = self._settings.scraping_base_url
        season_slug = self._settings.scraping_season_slug

        async with ScrapingClient() as client:
            total = len(players)
            for idx, player in enumerate(players, start=1):
                logger.info(
                    "PhotoDownloader: %d/%d slug=%s", idx, total, player.slug
                )

                page_url = f"{base_url}/jugadores/{player.slug}/{season_slug}"
                try:
                    html = await client.fetch(page_url)
                except ScrapingError as exc:
                    logger.warning(
                        "PhotoDownloader: page fetch failed slug=%s: %s",
                        player.slug,
                        exc,
                    )
                    errors += 1
                    continue

                photo_url = parse_player_photo(html)
                if not photo_url:
                    logger.debug(
                        "PhotoDownloader: no photo found for slug=%s", player.slug
                    )
                    skipped += 1
                    continue

                try:
                    img_bytes = await client.fetch_bytes(photo_url)
                except ScrapingError as exc:
                    logger.warning(
                        "PhotoDownloader: image download failed slug=%s url=%s: %s",
                        player.slug,
                        photo_url,
                        exc,
                    )
                    errors += 1
                    continue

                try:
                    img = Image.open(io.BytesIO(img_bytes))
                    img = img.convert("RGBA")
                    img = img.resize(PHOTO_SIZE, Image.LANCZOS)

                    out_path = _PHOTOS_DIR / f"{player.slug}.webp"
                    img.save(str(out_path), format="WEBP", quality=WEBP_QUALITY)
                except Exception as exc:
                    logger.warning(
                        "PhotoDownloader: image processing failed slug=%s: %s",
                        player.slug,
                        exc,
                    )
                    errors += 1
                    continue

                relative_path = f"players/{player.slug}.webp"
                await self.repo.update_player_photo(
                    player_id=player.id,
                    photo_path=relative_path,
                    source_url=photo_url,
                )
                downloaded += 1

        summary = {"downloaded": downloaded, "skipped": skipped, "errors": errors}
        logger.info("PhotoDownloader: done — %s", summary)
        return summary
