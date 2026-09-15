"""Refresh and read what futbolfantasy and analiticafantasy say about players."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.lineup_intel.matching import RosterPlayer, TeamRef, match_player, match_team
from src.features.lineup_intel.parsers import (
    SourcePlayer,
    parse_af_match,
    parse_af_matchday_links,
    parse_ff_team,
)
from src.features.lineup_intel.repository import LineupIntelRepository
from src.features.lineup_intel.schemas import (
    LineupIntelResponse,
    NewsItem,
    PlayerReadings,
    SourceReading,
    UnmatchedReading,
)
from src.features.scraping.client import ScrapingClient, ScrapingError
from src.shared.lineup_deadline import effective_deadline
from src.shared.models.matchday import Matchday
from src.shared.models.season import Season

logger = logging.getLogger(__name__)

FUTBOLFANTASY = "futbolfantasy"
ANALITICAFANTASY = "analiticafantasy"
SOURCES = (FUTBOLFANTASY, ANALITICAFANTASY)

FF_TEAM_URL = "https://www.futbolfantasy.com/laliga/equipos/{slug}"
AF_BASE_URL = "https://www.analiticafantasy.com"
AF_MATCHDAY_URL = (
    AF_BASE_URL + "/alineaciones-probables/la-liga/temporada-{year}/jornada-{matchday}"
)

#: The scheduled refresh acts only this close to the deadline of the matchday
#: being set: earlier, probable lineups are guesswork; after it, they change
#: nothing.
REFRESH_WINDOW = timedelta(hours=48)
#: Between two manual refreshes of the same matchday, so a button pressed
#: twice cannot hammer the sources.
REFRESH_COOLDOWN = timedelta(minutes=10)

_last_manual_refresh: dict[tuple[int, int], datetime] = {}


def enabled_sources() -> list[str]:
    wanted = {s.strip().lower() for s in (settings.lineup_intel_sources or "").split(",")}
    return [s for s in SOURCES if s in wanted]


def should_refresh(deadline: datetime | None, now: datetime) -> bool:
    """Whether the scheduled job acts: inside the last 48 h before the deadline."""
    return deadline is not None and deadline - REFRESH_WINDOW <= now < deadline


def claim_manual_refresh(season_id: int, matchday: int, now: datetime) -> None:
    """One manual refresh per matchday every REFRESH_COOLDOWN."""
    last = _last_manual_refresh.get((season_id, matchday))
    if last is not None and now - last < REFRESH_COOLDOWN:
        minutes = int((REFRESH_COOLDOWN - (now - last)).total_seconds() // 60) + 1
        raise BusinessRuleError(f"Se ha actualizado hace poco. Prueba dentro de {minutes} min.")
    _last_manual_refresh[(season_id, matchday)] = now


def season_start_year(name: str) -> int | None:
    """2026 for "2026-2027": analiticafantasy names seasons by their first year."""
    match = re.match(r"\s*(\d{4})", name or "")
    return int(match.group(1)) if match else None


class Fetcher(Protocol):
    async def fetch(self, url: str) -> str: ...


@dataclass
class SourceResult:
    rows: int = 0
    matched: int = 0
    news: int = 0
    errors: list[str] = field(default_factory=list)


def _row(
    season_id: int,
    matchday: int,
    source: str,
    team_id: int,
    player_id: int | None,
    raw_name: str,
    player: SourcePlayer,
) -> dict[str, Any]:
    return {
        "season_id": season_id,
        "matchday_number": matchday,
        "source": source,
        "team_id": team_id,
        "player_id": player_id,
        "raw_name": raw_name[:120],
        "probability": player.probability,
        "starter": player.starter,
        "status": player.status,
        "note": player.note,
    }


def _unique(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """First row per key: one INSERT … ON CONFLICT cannot touch a row twice."""
    seen: dict[Any, dict[str, Any]] = {}
    for row in rows:
        seen.setdefault(row[key], row)
    return list(seen.values())


class LineupIntelService:
    def __init__(
        self,
        session: AsyncSession,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.session = session
        self.repo = LineupIntelRepository(session)
        self._client_factory = client_factory or ScrapingClient

    async def refresh(
        self, season_id: int, matchday: int, now: datetime | None = None
    ) -> dict[str, SourceResult]:
        season = await self.session.get(Season, season_id)
        if season is None:
            raise NotFoundError("Temporada", season_id)
        now = now or datetime.now(UTC)
        teams = await self.repo.teams(season_id)
        roster = await self.repo.roster(season_id)

        results: dict[str, SourceResult] = {}
        async with self._client_factory() as client:
            for source in enabled_sources():
                result = results.setdefault(source, SourceResult())
                try:
                    if source == FUTBOLFANTASY:
                        await self._futbolfantasy(
                            client, season_id, matchday, teams, roster, now, result
                        )
                    else:
                        await self._analiticafantasy(
                            client, season, matchday, teams, roster, result
                        )
                except Exception as exc:
                    # One source down must not take the other with it.
                    logger.exception("lineup_intel: %s refresh failed", source)
                    result.errors.append(f"{source}: {exc}")
        await self.session.commit()
        logger.info(
            "lineup_intel: season=%d md=%d %s",
            season_id,
            matchday,
            {k: (v.rows, v.matched, v.news, len(v.errors)) for k, v in results.items()},
        )
        return results

    async def _futbolfantasy(
        self,
        client: Fetcher,
        season_id: int,
        matchday: int,
        teams: list[TeamRef],
        roster: list[RosterPlayer],
        now: datetime,
        result: SourceResult,
    ) -> None:
        # futbolfantasy's slugs are ours: no name matching needed.
        by_slug = {p.slug: p.id for p in roster}
        for team in teams:
            try:
                html = await client.fetch(FF_TEAM_URL.format(slug=team.slug))
            except ScrapingError as exc:
                result.errors.append(f"{team.slug}: {exc}")
                continue
            players, news = parse_ff_team(html, now)
            team_roster = [p for p in roster if p.team_id == team.id]
            rows = []
            for player in players:
                # No slug means no page of his own there: match by name instead.
                player_id = (
                    by_slug.get(player.slug) if player.slug else match_player(player, team_roster)
                )
                result.matched += player_id is not None
                rows.append(
                    _row(
                        season_id,
                        matchday,
                        FUTBOLFANTASY,
                        team.id,
                        player_id,
                        player.slug or player.name,
                        player,
                    )
                )
            rows = _unique(rows, "raw_name")
            await self.repo.save_team_readings(
                season_id=season_id,
                matchday=matchday,
                source=FUTBOLFANTASY,
                team_id=team.id,
                rows=rows,
            )
            result.rows += len(rows)
            news_rows = _unique(
                [
                    {
                        "season_id": season_id,
                        "team_id": team.id,
                        "source": FUTBOLFANTASY,
                        "title": item.title,
                        "url": item.url[:500],
                        "published_at": item.published_at,
                    }
                    for item in news
                ],
                "url",
            )
            await self.repo.save_news(news_rows)
            result.news += len(news_rows)

    async def _analiticafantasy(
        self,
        client: Fetcher,
        season: Season,
        matchday: int,
        teams: list[TeamRef],
        roster: list[RosterPlayer],
        result: SourceResult,
    ) -> None:
        year = season_start_year(season.name)
        if year is None:
            result.errors.append(f"sin año en el nombre de la temporada: {season.name!r}")
            return
        html = await client.fetch(AF_MATCHDAY_URL.format(year=year, matchday=matchday))
        links = parse_af_matchday_links(html)
        if not links:
            result.errors.append("la jornada no lista partidos")
            return
        for link in links:
            try:
                page = await client.fetch(AF_BASE_URL + link)
            except ScrapingError as exc:
                result.errors.append(f"{link}: {exc}")
                continue
            parsed = parse_af_match(page)
            if parsed is None:
                result.errors.append(f"{link}: sin alineaciones legibles")
                continue
            for side in parsed:
                team_id = match_team(side.name, teams)
                if team_id is None:
                    result.errors.append(f"equipo sin emparejar: {side.name}")
                    continue
                team_roster = [p for p in roster if p.team_id == team_id]
                rows = []
                for player in side.players:
                    player_id = match_player(player, team_roster)
                    result.matched += player_id is not None
                    rows.append(
                        _row(
                            season.id,
                            matchday,
                            ANALITICAFANTASY,
                            team_id,
                            player_id,
                            player.name,
                            player,
                        )
                    )
                rows = _unique(rows, "raw_name")
                await self.repo.save_team_readings(
                    season_id=season.id,
                    matchday=matchday,
                    source=ANALITICAFANTASY,
                    team_id=team_id,
                    rows=rows,
                )
                result.rows += len(rows)

    async def read(self, season_id: int, matchday: int) -> LineupIntelResponse:
        readings = await self.repo.readings(season_id, matchday)
        by_player: dict[int, list[SourceReading]] = {}
        unmatched: list[UnmatchedReading] = []
        for row in readings:
            reading = SourceReading(
                source=row.source,
                probability=row.probability,
                previous_probability=row.previous_probability,
                starter=row.starter,
                status=row.status,
                note=row.note,
                fetched_at=row.fetched_at,
            )
            if row.player_id is None:
                unmatched.append(
                    UnmatchedReading(team_id=row.team_id, raw_name=row.raw_name, reading=reading)
                )
            else:
                by_player.setdefault(row.player_id, []).append(reading)
        news = await self.repo.news(season_id)
        return LineupIntelResponse(
            season_id=season_id,
            matchday_number=matchday,
            updated_at=max((row.fetched_at for row in readings), default=None),
            players=[
                PlayerReadings(player_id=pid, readings=sorted(items, key=lambda r: r.source))
                for pid, items in by_player.items()
            ],
            unmatched=unmatched,
            news=[
                NewsItem(
                    team_id=item.team_id,
                    source=item.source,
                    title=item.title,
                    url=item.url,
                    published_at=item.published_at,
                )
                for item in news
            ],
        )


async def refresh_current_matchday() -> None:
    """Scheduler job: refresh the matchday being set, inside the 48 h window."""
    from src.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            season = (
                await session.execute(
                    select(Season)
                    .where(Season.status == "active", Season.kind == "league")
                    .order_by(Season.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if season is None or season.matchday_current <= 0:
                return
            matchday = (
                await session.execute(
                    select(Matchday).where(
                        Matchday.season_id == season.id,
                        Matchday.number == season.matchday_current,
                    )
                )
            ).scalar_one_or_none()
            if matchday is None:
                return
            deadline = effective_deadline(matchday, season.lineup_deadline_min)
            if not should_refresh(deadline, datetime.now(UTC)):
                return
            await LineupIntelService(session).refresh(season.id, matchday.number)
    except Exception:
        logger.exception("lineup_intel: scheduled refresh failed")
