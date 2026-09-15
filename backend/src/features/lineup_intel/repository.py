"""Database access for what external sources say about players."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineup_intel.matching import RosterPlayer, TeamRef
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_availability import PlayerAvailability, TeamNews
from src.shared.models.team import Team


class LineupIntelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def teams(self, season_id: int) -> list[TeamRef]:
        result = await self.session.execute(
            select(Team.id, Team.name, Team.slug, Team.short_name).where(
                Team.season_id == season_id
            )
        )
        return [
            TeamRef(id=r.id, name=r.name, slug=r.slug, short_name=r.short_name) for r in result
        ]

    async def roster(self, season_id: int) -> list[RosterPlayer]:
        result = await self.session.execute(
            select(
                Player.id,
                Player.team_id,
                Player.display_name,
                Player.slug,
                Player.position,
                Player.aliases,
            ).where(Player.season_id == season_id)
        )
        return [
            RosterPlayer(
                id=r.id,
                team_id=r.team_id,
                display_name=r.display_name,
                slug=r.slug,
                position=r.position,
                aliases=r.aliases,
            )
            for r in result
        ]

    async def save_team_readings(
        self,
        *,
        season_id: int,
        matchday: int,
        source: str,
        team_id: int,
        rows: list[dict[str, Any]],
    ) -> None:
        """Upsert what a source says about a team, and drop the names it no
        longer lists.

        Only ever called with a non-empty reading: a page that failed to parse
        must leave the last good data in place, not wipe it. The previous
        probability is kept only when the probability changes, so "up from 50 %"
        survives refreshes that bring nothing new.
        """
        if not rows:
            return
        table = PlayerAvailability.__table__
        stmt = pg_insert(PlayerAvailability).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_player_availability",
            set_={
                "player_id": stmt.excluded.player_id,
                "previous_probability": case(
                    (
                        table.c.probability.is_distinct_from(stmt.excluded.probability),
                        table.c.probability,
                    ),
                    else_=table.c.previous_probability,
                ),
                "probability": stmt.excluded.probability,
                "starter": stmt.excluded.starter,
                "status": stmt.excluded.status,
                "note": stmt.excluded.note,
                "fetched_at": func.now(),
            },
        )
        await self.session.execute(stmt)
        await self.session.execute(
            delete(PlayerAvailability).where(
                PlayerAvailability.season_id == season_id,
                PlayerAvailability.matchday_number == matchday,
                PlayerAvailability.source == source,
                PlayerAvailability.team_id == team_id,
                PlayerAvailability.raw_name.not_in([row["raw_name"] for row in rows]),
            )
        )

    async def save_news(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        stmt = pg_insert(TeamNews).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_team_news_team_url",
            set_={
                "title": stmt.excluded.title,
                "published_at": stmt.excluded.published_at,
                "fetched_at": func.now(),
            },
        )
        await self.session.execute(stmt)

    async def readings(self, season_id: int, matchday: int) -> list[PlayerAvailability]:
        result = await self.session.execute(
            select(PlayerAvailability)
            .where(
                PlayerAvailability.season_id == season_id,
                PlayerAvailability.matchday_number == matchday,
            )
            .order_by(
                PlayerAvailability.team_id, PlayerAvailability.source, PlayerAvailability.raw_name
            )
        )
        return list(result.scalars())

    async def match_source_urls(self, season_id: int, matchday: int) -> list[str]:
        """futbolfantasy URLs of the matchday's matches. predicted11 uses the
        same ``{id}-{slug}`` for its match pages."""
        result = await self.session.execute(
            select(Match.source_url)
            .join(Matchday, Matchday.id == Match.matchday_id)
            .where(
                Matchday.season_id == season_id,
                Matchday.number == matchday,
                Match.source_url.is_not(None),
            )
            .order_by(Match.id)
        )
        return [url for url in result.scalars() if url]

    async def last_fetched(
        self, season_id: int, matchday: int, source_prefix: str
    ) -> datetime | None:
        """When sources starting with ``source_prefix`` were last read."""
        result = await self.session.execute(
            select(func.max(PlayerAvailability.fetched_at)).where(
                PlayerAvailability.season_id == season_id,
                PlayerAvailability.matchday_number == matchday,
                PlayerAvailability.source.startswith(source_prefix),
            )
        )
        return result.scalar_one_or_none()

    async def news(self, season_id: int, per_team: int = 5) -> list[TeamNews]:
        """The latest headlines of each team, newest first."""
        result = await self.session.execute(
            select(TeamNews)
            .where(TeamNews.season_id == season_id)
            .order_by(TeamNews.published_at.desc().nulls_last(), TeamNews.id.desc())
        )
        kept: list[TeamNews] = []
        per: dict[int, int] = {}
        for item in result.scalars():
            if per.get(item.team_id, 0) < per_team:
                kept.append(item)
                per[item.team_id] = per.get(item.team_id, 0) + 1
        return kept
