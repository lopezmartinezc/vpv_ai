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


scraping_settings = ScrapingSettings()
