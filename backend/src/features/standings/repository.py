from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.user import User


@dataclass
class StandingRow:
    participant_id: int
    display_name: str
    total_points: int
    matchdays_played: int


class StandingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_standings(self, season_id: int) -> list[StandingRow]:
        stmt = (
            select(
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                func.coalesce(
                    func.sum(
                        case(
                            (Matchday.counts.is_(True), ParticipantMatchdayScore.total_points),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_points"),
                func.count(
                    case(
                        (Matchday.counts.is_(True), ParticipantMatchdayScore.id),
                    )
                ).label("matchdays_played"),
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .outerjoin(
                ParticipantMatchdayScore,
                ParticipantMatchdayScore.participant_id == SeasonParticipant.id,
            )
            .outerjoin(
                Matchday,
                ParticipantMatchdayScore.matchday_id == Matchday.id,
            )
            .where(SeasonParticipant.season_id == season_id)
            .group_by(SeasonParticipant.id, User.display_name)
            .order_by(
                func.sum(
                    case(
                        (Matchday.counts.is_(True), ParticipantMatchdayScore.total_points),
                        else_=0,
                    )
                )
                .desc()
                .nulls_last()
            )
        )
        result = await self.session.execute(stmt)
        return [
            StandingRow(
                participant_id=row.participant_id,
                display_name=row.display_name,
                total_points=int(row.total_points),
                matchdays_played=int(row.matchdays_played),
            )
            for row in result.all()
        ]
