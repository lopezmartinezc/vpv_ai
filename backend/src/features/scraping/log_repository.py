from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.scraping_log import ScrapingLog


class ScrapingLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert(self, logs: list[dict]) -> int:
        """Insert a batch of log entries. Returns number inserted."""
        if not logs:
            return 0
        objects = [ScrapingLog(**entry) for entry in logs]
        self.session.add_all(objects)
        await self.session.flush()
        return len(objects)

    async def query(
        self,
        *,
        season_id: int,
        matchday_number: int | None = None,
        match_id: int | None = None,
        status: str | None = None,
        job_type: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Query logs with optional filters, returns dicts with player/match names."""
        from src.shared.models.matchday import Match
        from src.shared.models.player import Player
        from src.shared.models.team import Team

        home = Team.__table__.alias("home_team")
        away = Team.__table__.alias("away_team")

        stmt = (
            select(
                ScrapingLog.id,
                ScrapingLog.matchday_number,
                ScrapingLog.match_id,
                ScrapingLog.player_id,
                ScrapingLog.job_type,
                ScrapingLog.status,
                ScrapingLog.message,
                ScrapingLog.detail,
                ScrapingLog.created_at,
                Player.display_name.label("player_name"),
                home.c.short_name.label("home_team"),
                away.c.short_name.label("away_team"),
            )
            .outerjoin(Player, ScrapingLog.player_id == Player.id)
            .outerjoin(Match, ScrapingLog.match_id == Match.id)
            .outerjoin(home, Match.home_team_id == home.c.id)
            .outerjoin(away, Match.away_team_id == away.c.id)
            .where(ScrapingLog.season_id == season_id)
            .order_by(ScrapingLog.created_at.desc(), ScrapingLog.id.desc())
            .limit(limit)
            .offset(offset)
        )

        if matchday_number is not None:
            stmt = stmt.where(ScrapingLog.matchday_number == matchday_number)
        if match_id is not None:
            stmt = stmt.where(ScrapingLog.match_id == match_id)
        if status is not None:
            stmt = stmt.where(ScrapingLog.status == status)
        if job_type is not None:
            stmt = stmt.where(ScrapingLog.job_type == job_type)
        if search:
            stmt = stmt.where(ScrapingLog.message.ilike(f"%{search}%"))

        result = await self.session.execute(stmt)
        return [
            {
                "id": r.id,
                "matchday_number": r.matchday_number,
                "match_id": r.match_id,
                "player_id": r.player_id,
                "job_type": r.job_type,
                "status": r.status,
                "message": r.message,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "player_name": r.player_name,
                "match_label": f"{r.home_team} vs {r.away_team}"
                if r.home_team and r.away_team
                else None,
            }
            for r in result.all()
        ]

    async def count(
        self,
        *,
        season_id: int,
        matchday_number: int | None = None,
        match_id: int | None = None,
        status: str | None = None,
        job_type: str | None = None,
        search: str | None = None,
    ) -> int:
        """Count logs matching filters."""
        stmt = select(func.count(ScrapingLog.id)).where(ScrapingLog.season_id == season_id)

        if matchday_number is not None:
            stmt = stmt.where(ScrapingLog.matchday_number == matchday_number)
        if match_id is not None:
            stmt = stmt.where(ScrapingLog.match_id == match_id)
        if status is not None:
            stmt = stmt.where(ScrapingLog.status == status)
        if job_type is not None:
            stmt = stmt.where(ScrapingLog.job_type == job_type)
        if search:
            stmt = stmt.where(ScrapingLog.message.ilike(f"%{search}%"))

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def cleanup(self, days: int = 90) -> int:
        """Delete logs older than *days*. Returns count deleted."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = delete(ScrapingLog).where(ScrapingLog.created_at < cutoff)
        result = await self.session.execute(stmt)
        return getattr(result, "rowcount", 0) or 0
