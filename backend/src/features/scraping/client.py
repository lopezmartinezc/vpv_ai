from __future__ import annotations

import asyncio
import logging
import random
from types import TracebackType
from typing import Self

import httpx

from src.features.scraping.config import scraping_settings

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class ScrapingError(Exception):
    """Raised when all retry attempts for a URL are exhausted."""

    def __init__(self, url: str, cause: Exception) -> None:
        self.url = url
        self.cause = cause
        super().__init__(f"Failed to fetch {url!r}: {cause}")


class ScrapingClient:
    """Async HTTP client for scraping futbolfantasy.com.

    Features:
    - Configurable timeout via ScrapingSettings.
    - Browser-like User-Agent header to reduce block probability.
    - Automatic retry with exponential backoff (max 3 attempts by default).
    - Random delay between requests to avoid rate limiting.
    - Context manager support for proper resource cleanup.
    """

    def __init__(self) -> None:
        self._settings = scraping_settings
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._settings.scraping_timeout),
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch(self, url: str) -> str:
        """Fetch *url* and return the response body as an HTML string.

        Retries up to *scraping_max_retries* times with exponential backoff.
        Applies a random delay before each request (except the very first one
        of a session) so that the scraper mimics human browsing pace.

        Raises:
            ScrapingError: when all retry attempts are exhausted.
            RuntimeError: when called outside of an ``async with`` block.
        """
        if self._client is None:
            raise RuntimeError("ScrapingClient must be used as an async context manager.")

        max_attempts = self._settings.scraping_max_retries
        last_exc: Exception = RuntimeError("unreachable")

        for attempt in range(1, max_attempts + 1):
            # Apply a random delay before every attempt (including the first)
            # to be polite towards the server.
            delay = random.uniform(
                self._settings.scraping_delay_min,
                self._settings.scraping_delay_max,
            )
            await asyncio.sleep(delay)

            try:
                logger.debug("Fetching %s (attempt %d/%d)", url, attempt, max_attempts)
                response = await self._client.get(url)
                response.raise_for_status()
                logger.debug(
                    "Fetched %s — status=%d, bytes=%d",
                    url,
                    response.status_code,
                    len(response.content),
                )
                return response.text

            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "HTTP %d for %s (attempt %d/%d)",
                    exc.response.status_code,
                    url,
                    attempt,
                    max_attempts,
                )
                last_exc = exc
            except httpx.RequestError as exc:
                logger.warning(
                    "Request error for %s: %s (attempt %d/%d)",
                    url,
                    exc,
                    attempt,
                    max_attempts,
                )
                last_exc = exc

            # Exponential backoff before the next retry
            if attempt < max_attempts:
                backoff = 2.0**attempt
                logger.debug("Backoff %.1fs before retry", backoff)
                await asyncio.sleep(backoff)

        raise ScrapingError(url, last_exc)

    async def fetch_bytes(self, url: str) -> bytes:
        """Fetch *url* and return the raw response bytes (for images/binaries).

        No delay is applied — this is intended for CDN resources, not the main
        website.  Retries are still performed on failure.
        """
        if self._client is None:
            raise RuntimeError("ScrapingClient must be used as an async context manager.")

        max_attempts = self._settings.scraping_max_retries
        last_exc: Exception = RuntimeError("unreachable")

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                return response.content
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning(
                    "fetch_bytes: error for %s (attempt %d/%d): %s",
                    url,
                    attempt,
                    max_attempts,
                    exc,
                )
                last_exc = exc
                if attempt < max_attempts:
                    await asyncio.sleep(1.0)

        raise ScrapingError(url, last_exc)
