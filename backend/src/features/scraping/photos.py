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
from src.features.scraping.parsers import parse_player_photo, parse_player_position
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
        """Enrich every player in *season_id* that lacks a photo or a position.

        For each candidate, fetch the individual ``/jugadores/{slug}`` page and:
        1. Update ``players.position`` if it was missing.
        2. Resolve the photo URL (`parse_player_photo`), download the image,
           resize to 200x200 WebP, save under ``static/players/{slug}.webp``
           and update ``players.photo_path``.

        Files already on disk are restored to the DB without a re-download.

        Returns a summary dict with keys ``downloaded``, ``positions_set``,
        ``skipped``, ``errors``, ``restored``.
        """
        _PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

        players = await self.repo.get_players_to_enrich(season_id)
        logger.info("PhotoDownloader: %d players to enrich", len(players))

        downloaded = 0
        positions_set = 0
        skipped = 0
        errors = 0
        restored = 0

        # Restore photo_path for players whose WebP already exists on disk —
        # they still need an HTTP fetch if the position is missing, so we
        # don't drop them from the queue yet.
        for player in players:
            if player.photo_path:
                continue
            existing = _PHOTOS_DIR / f"{player.slug}.webp"
            if existing.exists():
                relative_path = f"players/{player.slug}.webp"
                await self.repo.update_player_photo(
                    player_id=player.id,
                    photo_path=relative_path,
                    source_url="",
                )
                player.photo_path = relative_path
                restored += 1
        if restored:
            await self.session.commit()
            logger.info("PhotoDownloader: restored %d photos from disk", restored)

        # Re-filter after restore — players whose only need was the photo and
        # had it on disk no longer require the HTTP fetch.
        players = [p for p in players if not p.photo_path or not p.position]

        base_url = self._settings.scraping_base_url

        async with ScrapingClient() as client:
            total = len(players)
            for idx, player in enumerate(players, start=1):
                logger.info("PhotoDownloader: %d/%d slug=%s", idx, total, player.slug)

                page_url = f"{base_url}/jugadores/{player.slug}"
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

                # Position — only set if currently empty/null.
                if not player.position:
                    pos = parse_player_position(html)
                    if pos:
                        await self.repo.update_player_position(player.id, pos)
                        player.position = pos
                        positions_set += 1

                # Photo — skip if we already have one.
                if player.photo_path:
                    continue

                photo_url = parse_player_photo(html)
                if not photo_url:
                    logger.debug("PhotoDownloader: no photo found for slug=%s", player.slug)
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
                    img: Image.Image = Image.open(io.BytesIO(img_bytes))
                    img = img.convert("RGBA")
                    img = img.resize(PHOTO_SIZE, Image.Resampling.LANCZOS)

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

        summary = {
            "downloaded": downloaded,
            "positions_set": positions_set,
            "skipped": skipped,
            "errors": errors,
            "restored": restored,
        }
        logger.info("PhotoDownloader: done — %s", summary)
        return summary
