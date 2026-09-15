"""Refresh and read what the probable-lineup sources say about players.

futbolfantasy and analiticafantasy publish each player's chance of starting.
predicted11 contributes the elevens of the three best predictors of each team,
its «Ranking destacado»: each eleven counts as one more source, 100 for the
players in it and 0 for the rest of that team.

predicted11 serves those elevens through an API whose robots.txt asks not to
be crawled (``Disallow: /``). Reading it was the league admin's decision. The
reads are kept rare — at most every P11_INTERVAL, or on demand — go through the
same polite client as the other sources, and ``LINEUP_INTEL_SOURCES`` switches
them off without a deploy. The visitor key the API wants is read from the
site's own script on every refresh, never stored here.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.lineup_intel.matching import RosterPlayer, TeamRef, match_player, match_team
from src.features.lineup_intel.parsers import (
    P11Predictor,
    SourcePlayer,
    parse_af_match,
    parse_af_matchday_links,
    parse_ff_team,
    parse_p11_guest_key,
    parse_p11_lineup,
    parse_p11_match,
    parse_p11_script_path,
)
from src.features.lineup_intel.repository import LineupIntelRepository
from src.features.lineup_intel.schemas import (
    LineupIntelResponse,
    NewsItem,
    PlayerReadings,
    SourceCoverage,
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
PREDICTED11 = "predicted11"
SOURCES = (FUTBOLFANTASY, ANALITICAFANTASY, PREDICTED11)

FF_TEAM_URL = "https://www.futbolfantasy.com/laliga/equipos/{slug}"
AF_BASE_URL = "https://www.analiticafantasy.com"
AF_MATCHDAY_URL = (
    AF_BASE_URL + "/alineaciones-probables/la-liga/temporada-{year}/jornada-{matchday}"
)
P11_BASE_URL = "https://www.predicted11.com"
P11_MATCH_URL = P11_BASE_URL + "/es/laliga/partido/{slug}"
P11_LINEUP_URL = (
    "https://frpg.predicted11.com/api/p11/jornada/{season}/{matchday}/{team}/{user}/{key}"
)

#: The scheduled refresh acts only this close to the deadline of the matchday
#: being set: earlier, probable lineups are guesswork; after it, they change
#: nothing.
REFRESH_WINDOW = timedelta(hours=48)
#: Between two manual refreshes of the same matchday, so a button pressed
#: twice cannot hammer the sources.
REFRESH_COOLDOWN = timedelta(minutes=10)
#: predicted11 is read at most this often by the scheduled job (about 71
#: requests each time); the button always reads it.
P11_INTERVAL = timedelta(hours=6)
#: Predictors of each team's «Ranking destacado» whose eleven is read.
P11_TOP = 3

_last_manual_refresh: dict[tuple[int, int], datetime] = {}
_background: set[asyncio.Task[None]] = set()


def p11_source(position: int) -> str:
    """``predicted11_1`` … ``predicted11_3``: one source per predictor."""
    return f"{PREDICTED11}_{position}"


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


def p11_note(position: int, predictor: P11Predictor, team_name: str) -> str:
    """ "watusi74, 1.º del destacado del Rayo Vallecano (81,8 % de acierto)"."""
    pct = f"{predictor.pct:.1f}".replace(".", ",")
    return f"{predictor.username}, {position}.º del destacado del {team_name} ({pct} % de acierto)"


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
        self,
        season_id: int,
        matchday: int,
        now: datetime | None = None,
        *,
        force_p11: bool = False,
    ) -> dict[str, SourceResult]:
        """Read every enabled source. predicted11 only if P11_INTERVAL has
        passed since its last read of this matchday, or ``force_p11``."""
        season = await self.session.get(Season, season_id)
        if season is None:
            raise NotFoundError("Temporada", season_id)
        now = now or datetime.now(UTC)
        teams = await self.repo.teams(season_id)
        roster = await self.repo.roster(season_id)

        sources = enabled_sources()
        if (
            PREDICTED11 in sources
            and not force_p11
            and not await self._p11_due(season_id, matchday, now)
        ):
            sources.remove(PREDICTED11)

        results: dict[str, SourceResult] = {}
        async with self._client_factory() as client:
            for source in sources:
                result = results.setdefault(source, SourceResult())
                try:
                    if source == FUTBOLFANTASY:
                        await self._futbolfantasy(
                            client, season_id, matchday, teams, roster, now, result
                        )
                    elif source == ANALITICAFANTASY:
                        await self._analiticafantasy(
                            client, season, matchday, teams, roster, result
                        )
                    else:
                        await self._predicted11(client, season_id, matchday, teams, roster, result)
                except Exception as exc:
                    # One source down must not take the others with it.
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

    async def _p11_due(self, season_id: int, matchday: int, now: datetime) -> bool:
        last = await self.repo.last_fetched(season_id, matchday, PREDICTED11)
        return last is None or now - last >= P11_INTERVAL

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

    async def _predicted11(
        self,
        client: Fetcher,
        season_id: int,
        matchday: int,
        teams: list[TeamRef],
        roster: list[RosterPlayer],
        result: SourceResult,
    ) -> None:
        """Each match page gives both teams' «Ranking destacado»; each of the
        top P11_TOP predictors' elevens comes from the API."""
        urls = await self.repo.match_source_urls(season_id, matchday)
        if not urls:
            result.errors.append("la jornada no tiene partidos con enlace de futbolfantasy")
            return
        by_id = {t.id: t for t in teams}
        key: str | None = None
        for source_url in urls:
            slug = source_url.rstrip("/").rsplit("/", 1)[-1]
            try:
                html = await client.fetch(P11_MATCH_URL.format(slug=slug))
            except ScrapingError as exc:
                result.errors.append(f"{slug}: {exc}")
                continue
            parsed = parse_p11_match(html)
            if parsed is None:
                result.errors.append(f"{slug}: sin datos legibles")
                continue
            if parsed.matchday != matchday:
                result.errors.append(f"{slug}: predicted11 lo pone en la J{parsed.matchday}")
                continue
            if key is None:
                key = await self._p11_key(client, html)
                if key is None:
                    result.errors.append("predicted11: sin la clave de visitante de su web")
                    return
            for side in parsed.sides:
                team_id = match_team(side.name, teams)
                if team_id is None:
                    result.errors.append(f"equipo sin emparejar: {side.name}")
                    continue
                team_roster = [p for p in roster if p.team_id == team_id]
                for position, predictor in enumerate(side.featured[:P11_TOP], start=1):
                    url = P11_LINEUP_URL.format(
                        season=parsed.season,
                        matchday=matchday,
                        team=side.team_id,
                        user=quote(predictor.username, safe=""),
                        key=key,
                    )
                    try:
                        lineup = parse_p11_lineup(await client.fetch(url))
                    except ScrapingError as exc:
                        result.errors.append(f"{predictor.username}: {exc}")
                        continue
                    # No eleven for this team: that predictor does not count.
                    if lineup is None or not lineup.players:
                        continue
                    note = p11_note(position, predictor, by_id[team_id].name)
                    rows = []
                    for player in lineup.players:
                        player_id = match_player(player, team_roster)
                        result.matched += player_id is not None
                        rows.append(
                            _row(
                                season_id,
                                matchday,
                                p11_source(position),
                                team_id,
                                player_id,
                                player.name,
                                replace(player, note=note),
                            )
                        )
                    rows = _unique(rows, "raw_name")
                    await self.repo.save_team_readings(
                        season_id=season_id,
                        matchday=matchday,
                        source=p11_source(position),
                        team_id=team_id,
                        rows=rows,
                    )
                    result.rows += len(rows)

    async def _p11_key(self, client: Fetcher, html: str) -> str | None:
        path = parse_p11_script_path(html)
        if path is None:
            return None
        try:
            return parse_p11_guest_key(await client.fetch(P11_BASE_URL + path))
        except ScrapingError:
            return None

    async def read(self, season_id: int, matchday: int) -> LineupIntelResponse:
        readings = await self.repo.readings(season_id, matchday)
        by_player: dict[int, list[SourceReading]] = {}
        unmatched: list[UnmatchedReading] = []
        coverage: dict[tuple[str, int], str | None] = {}
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
            if row.source.startswith(PREDICTED11):
                coverage.setdefault((row.source, row.team_id), row.note)
            if row.player_id is None:
                unmatched.append(
                    UnmatchedReading(team_id=row.team_id, raw_name=row.raw_name, reading=reading)
                )
            else:
                by_player.setdefault(row.player_id, []).append(reading)
        news = await self.repo.news(season_id)
        team_names = {t.id: t.name for t in await self.repo.teams(season_id)}
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
            coverage=[
                SourceCoverage(
                    source=source,
                    team_id=team_id,
                    team_name=team_names.get(team_id, ""),
                    note=note,
                )
                for (source, team_id), note in sorted(coverage.items())
            ],
        )


def start_background_refresh(season_id: int, matchday: int) -> None:
    """Run a manual refresh after the request returns: with predicted11 it
    takes minutes, longer than the proxy lets a request wait."""
    task = asyncio.create_task(_background_refresh(season_id, matchday))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _background_refresh(season_id: int, matchday: int) -> None:
    from src.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            await LineupIntelService(session).refresh(season_id, matchday, force_p11=True)
    except Exception:
        logger.exception("lineup_intel: background refresh failed")


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
