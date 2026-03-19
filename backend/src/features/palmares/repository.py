from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.season import Season
from src.shared.models.user import User


@dataclass
class StandingRow:
    season_id: int
    season_name: str
    user_id: int
    display_name: str
    total_points: int
    matchdays_played: int
    rank: int


@dataclass
class RecordRow:
    user_id: int
    display_name: str
    season_name: str
    matchday_number: int
    total_points: int


class PalmaresRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all_standings(self) -> list[StandingRow]:
        """Get ranked standings for every season (finished + active)."""
        total_pts = func.coalesce(
            func.sum(
                case(
                    (Matchday.counts.is_(True), ParticipantMatchdayScore.total_points),
                    else_=0,
                )
            ),
            0,
        ).label("total_points")

        md_played = func.count(
            case((Matchday.counts.is_(True), ParticipantMatchdayScore.id))
        ).label("matchdays_played")

        rn = (
            func.row_number()
            .over(
                partition_by=Season.id,
                order_by=total_pts.desc(),
            )
            .label("rn")
        )

        inner = (
            select(
                Season.id.label("season_id"),
                Season.name.label("season_name"),
                User.id.label("user_id"),
                User.display_name,
                total_pts,
                md_played,
                rn,
            )
            .join(SeasonParticipant, SeasonParticipant.season_id == Season.id)
            .join(User, SeasonParticipant.user_id == User.id)
            .outerjoin(
                ParticipantMatchdayScore,
                ParticipantMatchdayScore.participant_id == SeasonParticipant.id,
            )
            .outerjoin(
                Matchday,
                ParticipantMatchdayScore.matchday_id == Matchday.id,
            )
            .where(Season.status.in_(["finished", "active"]))
            .group_by(Season.id, Season.name, User.id, User.display_name)
            .subquery()
        )

        stmt = select(
            inner.c.season_id,
            inner.c.season_name,
            inner.c.user_id,
            inner.c.display_name,
            inner.c.total_points,
            inner.c.matchdays_played,
            inner.c.rn,
        ).order_by(inner.c.season_id.desc(), inner.c.rn)

        result = await self.session.execute(stmt)
        return [
            StandingRow(
                season_id=r.season_id,
                season_name=r.season_name,
                user_id=r.user_id,
                display_name=r.display_name,
                total_points=r.total_points,
                matchdays_played=r.matchdays_played,
                rank=r.rn,
            )
            for r in result.all()
        ]

    async def get_best_matchday_score(self) -> RecordRow | None:
        """Best single matchday score across all seasons."""
        return await self._matchday_extreme("max")

    async def get_worst_matchday_score(self) -> RecordRow | None:
        """Worst single matchday score across all seasons (where > 0)."""
        return await self._matchday_extreme("min")

    async def _matchday_extreme(self, direction: str) -> RecordRow | None:
        order = (
            ParticipantMatchdayScore.total_points.desc()
            if direction == "max"
            else ParticipantMatchdayScore.total_points.asc()
        )

        stmt = (
            select(
                User.id.label("user_id"),
                User.display_name,
                Season.name.label("season_name"),
                Matchday.number.label("matchday_number"),
                ParticipantMatchdayScore.total_points,
            )
            .join(
                SeasonParticipant,
                ParticipantMatchdayScore.participant_id == SeasonParticipant.id,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .join(Matchday, ParticipantMatchdayScore.matchday_id == Matchday.id)
            .join(Season, Matchday.season_id == Season.id)
            .where(
                Matchday.counts.is_(True),
                ParticipantMatchdayScore.total_points > 0,
            )
            .order_by(order)
            .limit(1)
        )

        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            return None

        return RecordRow(
            user_id=row.user_id,
            display_name=row.display_name,
            season_name=row.season_name,
            matchday_number=row.matchday_number,
            total_points=row.total_points,
        )
