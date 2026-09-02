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


VALID_STATS_SOURCES = ("player_page", "match_page")


def position_writes_allowed(
    matchday_start: int,
    matchday_winter: int | None,
    current_md: int,
) -> bool:
    """Whether a futbolfantasy-driven position CHANGE may be applied now.

    Business rule: a player's VPV position is frozen at the preseason draft
    and re-synced only at the winter draft. So source-driven position changes
    are allowed only in two windows:

    - Pre-draft, before counting begins (``current_md < matchday_start``).
    - The winter re-sync, at the winter-draft matchday
      (``current_md == matchday_winter``).

    Outside these, callers must ignore changes and only FILL empty positions
    (new signings). ``current_md`` is the season's latest played matchday
    (0 when nothing has been played yet → pre-draft).
    """
    if current_md < matchday_start:
        return True
    # Winter re-sync: one pass at the winter-draft matchday.
    return matchday_winter is not None and current_md == matchday_winter


def stats_source_for(tournament_config: dict | None) -> str:
    """Return the stats-source strategy for a season.

    "player_page" (default) keeps the historic flow: fetch each player's
    individual stats page and look for the per-matchday `jorn-td` row.

    "match_page" is used for tournaments whose player pages don't carry
    a per-jornada table (Mundial, Eurocopa, ...). The scraper instead
    fetches each match's source URL once and parses the in-page table
    that lists all 52 players + raw stats.

    Tournament admins opt-in by setting
    ``seasons.tournament_config = {"stats_source": "match_page", ...}``.
    """
    if not tournament_config:
        return "player_page"
    candidate = tournament_config.get("stats_source")
    if candidate in VALID_STATS_SOURCES:
        return candidate
    return "player_page"


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
