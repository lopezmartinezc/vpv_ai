from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Subquery

from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_ownership_log import PlayerOwnershipLog
from src.shared.models.player_stat import PlayerStat
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.team import Team
from src.shared.models.user import User


@dataclass
class SquadSummaryRow:
    participant_id: int
    display_name: str
    total_players: int
    season_points: int
    por: int
    defe: int
    med: int
    dele: int


@dataclass
class SquadPlayerRow:
    player_id: int
    display_name: str
    photo_path: str | None
    position: str
    team_name: str
    season_points: int


POSITION_ORDER = case(
    (Player.position == "POR", 1),
    (Player.position == "DEF", 2),
    (Player.position == "MED", 3),
    (Player.position == "DEL", 4),
    else_=5,
)


def _ownership_at_matchday(season_id: int, matchday_number: int) -> Subquery:
    """Subquery: effective owner of each player at a given matchday.

    Returns (player_id, participant_id) using the most recent ownership log
    entry where from_matchday <= matchday_number.
    """
    # Row-number window: latest entry per player
    row_num = (
        func.row_number()
        .over(
            partition_by=PlayerOwnershipLog.player_id,
            order_by=PlayerOwnershipLog.from_matchday.desc(),
        )
        .label("rn")
    )

    inner = (
        select(
            PlayerOwnershipLog.player_id,
            PlayerOwnershipLog.participant_id,
            row_num,
        )
        .where(
            PlayerOwnershipLog.season_id == season_id,
            PlayerOwnershipLog.from_matchday <= matchday_number,
        )
        .subquery()
    )

    return select(inner.c.player_id, inner.c.participant_id).where(inner.c.rn == 1).subquery()


class SquadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_squads(
        self,
        season_id: int,
        matchday_number: int | None = None,
    ) -> list[SquadSummaryRow]:
        # Subquery: position counts per participant
        if matchday_number is not None:
            ownership = _ownership_at_matchday(season_id, matchday_number)
            player_counts = (
                select(
                    ownership.c.participant_id,
                    func.count(Player.id).label("total_players"),
                    func.count(Player.id).filter(Player.position == "POR").label("por"),
                    func.count(Player.id).filter(Player.position == "DEF").label("defe"),
                    func.count(Player.id).filter(Player.position == "MED").label("med"),
                    func.count(Player.id).filter(Player.position == "DEL").label("dele"),
                )
                .join(Player, Player.id == ownership.c.player_id)
                .where(ownership.c.participant_id.isnot(None))
                .group_by(ownership.c.participant_id)
                .subquery()
            )
        else:
            player_counts = (
                select(
                    Player.owner_id.label("participant_id"),
                    func.count(Player.id).label("total_players"),
                    func.count(Player.id).filter(Player.position == "POR").label("por"),
                    func.count(Player.id).filter(Player.position == "DEF").label("defe"),
                    func.count(Player.id).filter(Player.position == "MED").label("med"),
                    func.count(Player.id).filter(Player.position == "DEL").label("dele"),
                )
                .where(Player.season_id == season_id, Player.owner_id.isnot(None))
                .group_by(Player.owner_id)
                .subquery()
            )

        # Subquery: season points from participant_matchday_scores (counts=true)
        season_pts = (
            select(
                ParticipantMatchdayScore.participant_id,
                func.coalesce(
                    func.sum(ParticipantMatchdayScore.total_points),
                    0,
                ).label("season_points"),
            )
            .join(Matchday, ParticipantMatchdayScore.matchday_id == Matchday.id)
            .where(Matchday.season_id == season_id, Matchday.counts.is_(True))
            .group_by(ParticipantMatchdayScore.participant_id)
            .subquery()
        )

        stmt = (
            select(
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                func.coalesce(player_counts.c.total_players, 0).label("total_players"),
                func.coalesce(season_pts.c.season_points, 0).label("season_points"),
                func.coalesce(player_counts.c.por, 0).label("por"),
                func.coalesce(player_counts.c.defe, 0).label("defe"),
                func.coalesce(player_counts.c.med, 0).label("med"),
                func.coalesce(player_counts.c.dele, 0).label("dele"),
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .outerjoin(
                player_counts,
                player_counts.c.participant_id == SeasonParticipant.id,
            )
            .outerjoin(
                season_pts,
                season_pts.c.participant_id == SeasonParticipant.id,
            )
            .where(SeasonParticipant.season_id == season_id)
            .order_by(func.coalesce(season_pts.c.season_points, 0).desc())
        )

        result = await self.session.execute(stmt)
        return [
            SquadSummaryRow(
                participant_id=row.participant_id,
                display_name=row.display_name,
                total_players=row.total_players,
                season_points=row.season_points,
                por=row.por,
                defe=row.defe,
                med=row.med,
                dele=row.dele,
            )
            for row in result.all()
        ]

    async def get_squad_players(
        self,
        season_id: int,
        participant_id: int,
        matchday_number: int | None = None,
    ) -> list[SquadPlayerRow]:
        # Season points per player: SUM(pts_total) WHERE matchday.counts=true
        season_pts = func.coalesce(
            func.sum(
                case(
                    (Matchday.counts.is_(True), PlayerStat.pts_total),
                    else_=0,
                ),
            ),
            0,
        ).label("season_points")

        base = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.photo_path,
                Player.position,
                Team.name.label("team_name"),
                season_pts,
            )
            .join(Team, Player.team_id == Team.id)
            .outerjoin(PlayerStat, PlayerStat.player_id == Player.id)
            .outerjoin(
                Matchday,
                and_(
                    PlayerStat.matchday_id == Matchday.id,
                    Matchday.season_id == season_id,
                ),
            )
        )

        if matchday_number is not None:
            ownership = _ownership_at_matchday(season_id, matchday_number)
            base = base.join(
                ownership,
                and_(
                    ownership.c.player_id == Player.id,
                    ownership.c.participant_id == participant_id,
                ),
            ).where(Player.season_id == season_id)
        else:
            base = base.where(
                Player.season_id == season_id,
                Player.owner_id == participant_id,
            )

        stmt = base.group_by(
            Player.id,
            Player.display_name,
            Player.photo_path,
            Player.position,
            Team.name,
        ).order_by(POSITION_ORDER.asc(), season_pts.desc())

        result = await self.session.execute(stmt)
        return [
            SquadPlayerRow(
                player_id=row.player_id,
                display_name=row.display_name,
                photo_path=row.photo_path,
                position=row.position,
                team_name=row.team_name,
                season_points=row.season_points,
            )
            for row in result.all()
        ]

    async def get_participant_display_name(
        self,
        participant_id: int,
    ) -> str | None:
        stmt = (
            select(User.display_name)
            .join(SeasonParticipant, SeasonParticipant.user_id == User.id)
            .where(SeasonParticipant.id == participant_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_participant_season_points(
        self,
        season_id: int,
        participant_id: int,
    ) -> int:
        stmt = (
            select(
                func.coalesce(
                    func.sum(ParticipantMatchdayScore.total_points),
                    0,
                ),
            )
            .join(Matchday, ParticipantMatchdayScore.matchday_id == Matchday.id)
            .where(
                ParticipantMatchdayScore.participant_id == participant_id,
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
