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

    async def download_all(
        self,
        season_id: int,
        *,
        refresh: bool = False,
    ) -> dict[str, int]:
        """Enrich players in *season_id* with photo + VPV position.

        For each candidate, fetch the individual ``/jugadores/{slug}`` page and:
        1. Update ``players.position`` — when ``refresh`` is False, only
           when the field was empty; when ``refresh`` is True, whenever the
           parser returns a non-empty value that differs from the stored one
           (covers a player who changed position mid-tournament).
        2. Resolve the photo URL (`parse_player_photo`), download the image,
           resize to 200x200 WebP, save under ``static/players/{slug}.webp``
           and update ``players.photo_path``.

        Files already on disk are restored to the DB without a re-download.

        Parameters
        ----------
        refresh:
            When True, processes every active player in the season — useful
            when the official squad list shifts (positions changed, players
            cut). When False (default), only players missing photo or
            position get touched (cheaper, fully idempotent).

        Returns a summary dict with keys ``downloaded``, ``positions_set``,
        ``positions_updated``, ``skipped``, ``errors``, ``restored``.
        """
        _PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

        if refresh:
            # Process every available player so position changes propagate.
            all_players = await self.repo.get_players_for_season(season_id)
            players = [p for p in all_players if p.is_available]
        else:
            players = await self.repo.get_players_to_enrich(season_id)

        logger.info(
            "PhotoDownloader: %d players to process (refresh=%s)",
            len(players),
            refresh,
        )

        downloaded = 0
        positions_set = 0
        positions_updated = 0
        skipped = 0
        errors = 0
        restored = 0

        # Restore photo_path for players whose WebP already exists on disk —
        # they still need an HTTP fetch if the position is missing or we're
        # in refresh mode, so we don't drop them from the queue yet.
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

        # In refresh mode we always re-fetch even if both fields look OK,
        # so we can pick up position changes. Otherwise drop the ones whose
        # only need (photo) was met by the disk restore above.
        if not refresh:
            players = [p for p in players if not p.photo_path or not p.position]

        base_url = self._settings.scraping_base_url
        # Use the season's scraping slug as a URL suffix when set
        # (e.g. .../jugadores/{slug}/world-cup-2026). futbolfantasy serves
        # the season-specific position and the season-specific kit photo
        # on that page; the bare URL returns the player's last-known
        # position which is stale for the Mundial.
        season = await self.repo.get_season(season_id)
        url_suffix = f"/{season.scraping_slug}" if season and season.scraping_slug else ""

        async with ScrapingClient() as client:
            total = len(players)
            for idx, player in enumerate(players, start=1):
                logger.info("PhotoDownloader: %d/%d slug=%s", idx, total, player.slug)

                primary_url = f"{base_url}/jugadores/{player.slug}{url_suffix}"
                fallback_url = f"{base_url}/jugadores/{player.slug}" if url_suffix else None
                # Try the season-specific URL first; fall back to the bare
                # one on 404 (the season slug may be wrong, e.g.
                # 'world-cup' vs 'world-cup-2026').
                html = None
                for attempt_url in (primary_url, fallback_url):
                    if not attempt_url:
                        continue
                    try:
                        html = await client.fetch(attempt_url)
                        break
                    except ScrapingError as exc:
                        if attempt_url == primary_url and fallback_url:
                            logger.debug(
                                "PhotoDownloader: %s 4xx on suffix URL, falling back to bare URL",
                                player.slug,
                            )
                            continue
                        logger.warning(
                            "PhotoDownloader: page fetch failed slug=%s: %s",
                            player.slug,
                            exc,
                        )
                        errors += 1
                if html is None:
                    continue

                # Position — fill when missing, or update when refresh=True
                # and the parser returns a different non-empty value. Never
                # overwrite a stored position with None: a parser miss must
                # not erase good data.
                pos = parse_player_position(html)
                if pos:
                    if not player.position:
                        await self.repo.update_player_position(player.id, pos)
                        player.position = pos
                        positions_set += 1
                    elif refresh and pos != player.position:
                        logger.info(
                            "PhotoDownloader: %s position %s -> %s",
                            player.slug,
                            player.position,
                            pos,
                        )
                        await self.repo.update_player_position(player.id, pos)
                        player.position = pos
                        positions_updated += 1

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
            "positions_updated": positions_updated,
            "skipped": skipped,
            "errors": errors,
            "restored": restored,
        }
        logger.info("PhotoDownloader: done — %s", summary)
        return summary

    async def refresh_positions(
        self,
        season_id: int,
        concurrency: int = 5,
    ) -> dict[str, int]:
        """Fast pass: only re-check the VPV position for every active player.

        Same source URL strategy as :meth:`download_all` with refresh=True —
        prefer the season-specific page, fall back to the bare one on 404 —
        but skips the photo download and the Pillow conversion entirely and
        fans out the page fetches with ``asyncio.gather`` (semaphore-bounded
        concurrency). For a 1 300-player squad this typically completes in
        10-15 minutes instead of the ~70 of download_all --refresh.

        Returns ``{"checked", "positions_updated", "positions_set",
        "skipped", "errors"}``.
        """
        import asyncio

        all_players = await self.repo.get_players_for_season(season_id)
        players = [p for p in all_players if p.is_available]
        logger.info(
            "refresh_positions: %d active players, concurrency=%d",
            len(players),
            concurrency,
        )

        season = await self.repo.get_season(season_id)
        url_suffix = f"/{season.scraping_slug}" if season and season.scraping_slug else ""
        base_url = self._settings.scraping_base_url

        checked = 0
        positions_set = 0
        positions_updated = 0
        skipped = 0
        errors = 0
        # We collect updates in memory and apply them at the end on the
        # caller's session — avoids interleaving writes on the same
        # AsyncSession from multiple coroutines.
        updates: list[tuple[int, str]] = []
        sem = asyncio.Semaphore(concurrency)

        async with ScrapingClient() as client:

            async def _one(player) -> None:  # type: ignore[no-untyped-def]
                nonlocal checked, positions_set, positions_updated, skipped, errors
                async with sem:
                    primary_url = f"{base_url}/jugadores/{player.slug}{url_suffix}"
                    fallback_url = f"{base_url}/jugadores/{player.slug}" if url_suffix else None
                    html = None
                    for attempt_url in (primary_url, fallback_url):
                        if not attempt_url:
                            continue
                        try:
                            html = await client.fetch(attempt_url)
                            break
                        except ScrapingError:
                            if attempt_url == primary_url and fallback_url:
                                continue
                            errors += 1
                    if html is None:
                        return
                    checked += 1
                    pos = parse_player_position(html)
                    if not pos:
                        skipped += 1
                        return
                    if not player.position:
                        positions_set += 1
                        updates.append((player.id, pos))
                    elif pos != player.position:
                        logger.info(
                            "refresh_positions: %s position %s -> %s",
                            player.slug,
                            player.position,
                            pos,
                        )
                        positions_updated += 1
                        updates.append((player.id, pos))

            await asyncio.gather(*[_one(p) for p in players])

        # Persist accumulated updates on the caller's session.
        for player_id, pos in updates:
            await self.repo.update_player_position(player_id, pos)

        summary = {
            "checked": checked,
            "positions_set": positions_set,
            "positions_updated": positions_updated,
            "skipped": skipped,
            "errors": errors,
        }
        logger.info("refresh_positions: done — %s", summary)
        return summary
