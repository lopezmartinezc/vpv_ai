from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ScrapingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    scraping_base_url: str = "https://www.futbolfantasy.com"
    scraping_season_slug: str = "laliga-25-26"
    scraping_delay_min: float = 1.0
    scraping_delay_max: float = 4.0
    scraping_timeout: float = 15.0
    scraping_max_retries: int = 3

    # Scheduler settings
    scraping_poll_interval_seconds: int = 900  # 15 minutes between ticks
    scraping_buffer_minutes: int = 120  # minutes after played_at to consider match ended

    # Live match monitor
    live_monitor_interval_seconds: int = 60
    live_monitor_enabled: bool = True


scraping_settings = ScrapingSettings()


_TOURNAMENT_URL_PREFIX: dict[str, str] = {
    "mundial": "world-cup",
    "eurocopa": "eurocopa",
    "copa_america": "copa-america",
}


def competition_url_prefix(kind: str, tournament_type: str | None = None) -> str:
    """Return the futbolfantasy.com URL path segment for a competition.

    Examples:
        ('league', None)              -> 'laliga'
        ('tournament', 'mundial')     -> 'world-cup'
        ('tournament', 'eurocopa')    -> 'eurocopa'
        ('tournament', 'copa_america') -> 'copa-america'

    The URL prefix is the path segment after the host, e.g.
    https://www.futbolfantasy.com/world-cup/home for the World Cup.
    """
    if kind == "league":
        return "laliga"
    if kind == "tournament" and tournament_type:
        return _TOURNAMENT_URL_PREFIX.get(tournament_type, tournament_type)
    return "laliga"
