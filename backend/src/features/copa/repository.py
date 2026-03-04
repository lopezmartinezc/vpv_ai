from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player_stat import PlayerStat
from src.shared.models.user import User


@dataclass
class CopaRawRow:
    participant_id: int
    display_name: str
    matchday_number: int
    goals_for: int
    goals_against: int


class CopaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_copa_data(self, season_id: int) -> list[CopaRawRow]:
        """Get per-participant, per-matchday copa goals from lineup players."""
        stmt = (
            select(
                Lineup.participant_id,
                User.display_name,
                Matchday.number.label("matchday_number"),
                func.coalesce(
                    func.sum(PlayerStat.goals) + func.sum(PlayerStat.penalty_goals),
                    0,
                ).label("goals_for"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                PlayerStat.position == "POR",
                                func.coalesce(PlayerStat.goals_against, 0),
                            ),
                            else_=0,
                        )
                    )
                    + func.sum(func.coalesce(PlayerStat.own_goals, 0)),
                    0,
                ).label("goals_against"),
            )
            .join(LineupPlayer, LineupPlayer.lineup_id == Lineup.id)
            .join(Matchday, Lineup.matchday_id == Matchday.id)
            .join(
                SeasonParticipant,
                Lineup.participant_id == SeasonParticipant.id,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .join(
                PlayerStat,
                and_(
                    PlayerStat.player_id == LineupPlayer.player_id,
                    PlayerStat.matchday_id == Matchday.id,
                ),
            )
            .outerjoin(Match, PlayerStat.match_id == Match.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                # Respect match-level counts flag
                func.coalesce(Match.counts, True).is_(True),
            )
            .group_by(
                Lineup.participant_id,
                User.display_name,
                Matchday.number,
            )
            .order_by(Matchday.number.asc())
        )
        result = await self.session.execute(stmt)
        return [
            CopaRawRow(
                participant_id=row.participant_id,
                display_name=row.display_name,
                matchday_number=row.matchday_number,
                goals_for=int(row.goals_for),
                goals_against=int(row.goals_against),
            )
            for row in result.all()
        ]
