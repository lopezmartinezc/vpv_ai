"""Optional read-only queries; no connection is retained during model inference."""

import json
from dataclasses import asdict

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.features.stats.fixtures import FixtureStrengthService, difficulty
from src.features.stats.repository import StatsRepository

from .schemas import Position, StrictModel


class ExtraQuery(StrictModel):
    team: str = Field(default="", max_length=100)
    position: Position | None = None
    name: str = Field(default="", max_length=100)
    from_matchday: int = Field(default=1, strict=True, ge=1, le=100)
    limit: int = Field(default=15, strict=True, ge=1, le=30)


async def extra_query(season_id: int, tool: str, query: ExtraQuery) -> str:
    async with AsyncSessionLocal() as session, session.begin():
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        await session.execute(text("SET LOCAL statement_timeout = '8000ms'"))
        if tool == "calendario":
            fixtures = await FixtureStrengthService(session).fixtures(
                season_id, from_matchday=query.from_matchday, count=100
            )
            rows = [f for f in fixtures if query.team.lower() in f.team_name.lower()]
            data = [
                {
                    **asdict(f),
                    "difficulty": difficulty(query.position, f) if query.position else None,
                }
                for f in rows[: query.limit]
            ]
            return json.dumps({"total": len(rows), "rows": data}, ensure_ascii=False)
        return await performance(session, season_id, query)


async def performance(session: AsyncSession, season_id: int, query: ExtraQuery) -> str:
    stats = await StatsRepository(session).get_player_stats(season_id, include_noncounting=True)
    selected = [
        p
        for p in stats
        if query.team.lower() in p.team_name.lower()
        and query.name.lower() in p.display_name.lower()
        and (query.position is None or p.position == query.position)
    ]
    selected.sort(key=lambda p: p.total_points, reverse=True)
    return json.dumps(
        {
            "total": len(selected),
            "rows": [asdict(p) for p in selected[: query.limit]],
            "warning": "Datos observados, incluidas jornadas pre-draft. No son una proyección; cita PJ.",
        },
        ensure_ascii=False,
    )
