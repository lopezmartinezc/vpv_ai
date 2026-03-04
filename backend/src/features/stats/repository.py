"""Repository layer for admin statistics queries.

All queries filter on ``matchdays.counts IS TRUE`` so that disabled matchdays
(e.g. postponed rounds) are automatically excluded.

NOTE: ``marca_rating`` and ``as_picas`` are stored as ``String(10)`` and may
contain non-numeric values (e.g. star characters like "★★").  We use the
PostgreSQL regex operator ``~`` to validate the value before casting to Float.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Float, and_, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.team import Team
from src.shared.models.user import User

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PlayerStatRow:
    """Aggregated stats for a single player across all played matchdays."""

    player_id: int
    display_name: str
    photo_path: str | None
    position: str
    team_name: str
    goals: int
    penalty_goals: int
    own_goals: int
    assists: int
    penalties_saved: int
    yellow_cards: int
    red_cards: int  # Direct reds + double-yellow reds
    avg_marca: float | None  # May be None if all values are non-numeric
    avg_as: float | None
    minutes_played: int
    matchdays_played: int
    started_count: int
    avg_points: float
    total_points: int


@dataclass
class ParticipantBreakdownRow:
    """Point breakdown by scoring category for a participant's lined-up players."""

    participant_id: int
    display_name: str
    pts_play: int
    pts_result: int
    pts_clean_sheet: int
    pts_goals: int  # Includes penalty goals
    pts_assists: int
    pts_yellow: int
    pts_red: int
    pts_marca_as: int
    pts_total: int


@dataclass
class MatchdayScoreRow:
    """A single participant's total points in a specific matchday."""

    matchday_number: int
    participant_id: int
    display_name: str
    total_points: int


@dataclass
class FormationUsageRow:
    """How many times a formation was used across all lineups in a season."""

    formation: str
    usage_count: int


@dataclass
class MostLinedUpRow:
    """Player appearance count across all participants' lineups."""

    player_id: int
    display_name: str
    position: str
    team_name: str
    photo_path: str | None
    times_lined_up: int


@dataclass
class MatchdayAverageRow:
    """Aggregate point statistics (avg/max/min) for a matchday."""

    matchday_number: int
    avg_points: float
    max_points: int
    min_points: int


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class StatsRepository:
    """Read-only repository for aggregated season statistics.

    All methods accept a ``season_id`` and return dataclass rows.
    Queries only consider matchdays where ``counts=True`` and (where
    applicable) player_stats where ``played=True``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_player_stats(self, season_id: int) -> list[PlayerStatRow]:
        """Aggregate player-level stats grouped by player + position."""
        total_pts = func.coalesce(func.sum(PlayerStat.pts_total), 0)
        md_count = func.count(PlayerStat.id)
        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.photo_path,
                PlayerStat.position,
                Team.name.label("team_name"),
                func.coalesce(func.sum(PlayerStat.goals), 0).label("goals"),
                func.coalesce(func.sum(PlayerStat.penalty_goals), 0).label("penalty_goals"),
                func.coalesce(func.sum(PlayerStat.own_goals), 0).label("own_goals"),
                func.coalesce(func.sum(PlayerStat.assists), 0).label("assists"),
                func.coalesce(func.sum(PlayerStat.penalties_saved), 0).label("penalties_saved"),
                func.coalesce(
                    func.sum(
                        case(
                            (PlayerStat.yellow_card.is_(True), 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("yellow_cards"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                PlayerStat.red_card.is_(True) | PlayerStat.double_yellow.is_(True),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("red_cards"),
                func.avg(
                    case(
                        (
                            PlayerStat.marca_rating.op("~")(literal(r"^\d+(\.\d+)?$")),
                            func.cast(PlayerStat.marca_rating, Float),
                        ),
                        else_=None,
                    )
                ).label("avg_marca"),
                func.avg(
                    case(
                        (
                            PlayerStat.as_picas.op("~")(literal(r"^\d+(\.\d+)?$")),
                            func.cast(PlayerStat.as_picas, Float),
                        ),
                        else_=None,
                    )
                ).label("avg_as"),
                func.coalesce(func.sum(PlayerStat.minutes_played), 0).label("minutes_played"),
                md_count.label("matchdays_played"),
                func.coalesce(
                    func.sum(
                        case(
                            (PlayerStat.pts_starter > 0, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("started_count"),
                total_pts.label("total_points"),
            )
            .join(Player, PlayerStat.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .group_by(
                Player.id,
                Player.display_name,
                Player.photo_path,
                PlayerStat.position,
                Team.name,
            )
            .order_by(total_pts.desc())
        )
        result = await self.session.execute(stmt)
        return [
            PlayerStatRow(
                player_id=row.player_id,
                display_name=row.display_name,
                photo_path=row.photo_path,
                position=row.position,
                team_name=row.team_name,
                goals=int(row.goals),
                penalty_goals=int(row.penalty_goals),
                own_goals=int(row.own_goals),
                assists=int(row.assists),
                penalties_saved=int(row.penalties_saved),
                yellow_cards=int(row.yellow_cards),
                red_cards=int(row.red_cards),
                avg_marca=float(row.avg_marca) if row.avg_marca is not None else None,
                avg_as=float(row.avg_as) if row.avg_as is not None else None,
                minutes_played=int(row.minutes_played),
                matchdays_played=int(row.matchdays_played),
                started_count=int(row.started_count),
                avg_points=(
                    round(int(row.total_points) / int(row.matchdays_played), 2)
                    if int(row.matchdays_played) > 0
                    else 0.0
                ),
                total_points=int(row.total_points),
            )
            for row in result.all()
        ]

    async def get_participant_breakdowns(self, season_id: int) -> list[ParticipantBreakdownRow]:
        """Point breakdown per participant from their lined-up players.

        Joins: SeasonParticipant -> Lineup -> LineupPlayer -> PlayerStat
        (matched by player_id AND matchday_id to get the correct stat row).
        """
        stmt = (
            select(
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                func.coalesce(func.sum(PlayerStat.pts_play), 0).label("pts_play"),
                func.coalesce(func.sum(PlayerStat.pts_result), 0).label("pts_result"),
                func.coalesce(func.sum(PlayerStat.pts_clean_sheet), 0).label("pts_clean_sheet"),
                func.coalesce(
                    func.sum(PlayerStat.pts_goals + PlayerStat.pts_penalty_goals), 0
                ).label("pts_goals"),
                func.coalesce(func.sum(PlayerStat.pts_assists), 0).label("pts_assists"),
                func.coalesce(func.sum(PlayerStat.pts_yellow), 0).label("pts_yellow"),
                func.coalesce(func.sum(PlayerStat.pts_red), 0).label("pts_red"),
                func.coalesce(func.sum(PlayerStat.pts_marca_as), 0).label("pts_marca_as"),
                func.coalesce(func.sum(PlayerStat.pts_total), 0).label("pts_total"),
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .join(Lineup, Lineup.participant_id == SeasonParticipant.id)
            .join(LineupPlayer, LineupPlayer.lineup_id == Lineup.id)
            .join(Matchday, Lineup.matchday_id == Matchday.id)
            .join(
                PlayerStat,
                and_(
                    PlayerStat.player_id == LineupPlayer.player_id,
                    PlayerStat.matchday_id == Matchday.id,
                ),
            )
            .where(
                SeasonParticipant.season_id == season_id,
                Matchday.counts.is_(True),
            )
            .group_by(SeasonParticipant.id, User.display_name)
            .order_by(func.coalesce(func.sum(PlayerStat.pts_total), 0).desc())
        )
        result = await self.session.execute(stmt)
        return [
            ParticipantBreakdownRow(
                participant_id=row.participant_id,
                display_name=row.display_name,
                pts_play=int(row.pts_play),
                pts_result=int(row.pts_result),
                pts_clean_sheet=int(row.pts_clean_sheet),
                pts_goals=int(row.pts_goals),
                pts_assists=int(row.pts_assists),
                pts_yellow=int(row.pts_yellow),
                pts_red=int(row.pts_red),
                pts_marca_as=int(row.pts_marca_as),
                pts_total=int(row.pts_total),
            )
            for row in result.all()
        ]

    async def get_participant_matchday_scores(self, season_id: int) -> list[MatchdayScoreRow]:
        """Per-matchday scores from participant_matchday_scores table."""
        stmt = (
            select(
                Matchday.number.label("matchday_number"),
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                ParticipantMatchdayScore.total_points,
            )
            .join(Matchday, ParticipantMatchdayScore.matchday_id == Matchday.id)
            .join(
                SeasonParticipant,
                ParticipantMatchdayScore.participant_id == SeasonParticipant.id,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
            )
            .order_by(Matchday.number.asc(), SeasonParticipant.id.asc())
        )
        result = await self.session.execute(stmt)
        return [
            MatchdayScoreRow(
                matchday_number=row.matchday_number,
                participant_id=row.participant_id,
                display_name=row.display_name,
                total_points=int(row.total_points),
            )
            for row in result.all()
        ]

    async def get_formation_usage(self, season_id: int) -> list[FormationUsageRow]:
        """Count how many times each formation was used across all lineups."""
        stmt = (
            select(
                Lineup.formation,
                func.count(Lineup.id).label("usage_count"),
            )
            .join(Matchday, Lineup.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
            )
            .group_by(Lineup.formation)
            .order_by(func.count(Lineup.id).desc())
        )
        result = await self.session.execute(stmt)
        return [
            FormationUsageRow(
                formation=row.formation,
                usage_count=int(row.usage_count),
            )
            for row in result.all()
        ]

    async def get_most_lined_up(self, season_id: int, limit: int = 15) -> list[MostLinedUpRow]:
        """Top N players by number of appearances in any participant's lineup."""
        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.position,
                Team.name.label("team_name"),
                Player.photo_path,
                func.count(LineupPlayer.id).label("times_lined_up"),
            )
            .join(Lineup, LineupPlayer.lineup_id == Lineup.id)
            .join(Matchday, Lineup.matchday_id == Matchday.id)
            .join(Player, LineupPlayer.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
            )
            .group_by(
                Player.id,
                Player.display_name,
                Player.position,
                Team.name,
                Player.photo_path,
            )
            .order_by(func.count(LineupPlayer.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            MostLinedUpRow(
                player_id=row.player_id,
                display_name=row.display_name,
                position=row.position,
                team_name=row.team_name,
                photo_path=row.photo_path,
                times_lined_up=int(row.times_lined_up),
            )
            for row in result.all()
        ]

    async def get_matchday_averages(self, season_id: int) -> list[MatchdayAverageRow]:
        """Average, max, and min points per matchday across all participants."""
        stmt = (
            select(
                Matchday.number.label("matchday_number"),
                func.avg(ParticipantMatchdayScore.total_points).label("avg_points"),
                func.max(ParticipantMatchdayScore.total_points).label("max_points"),
                func.min(ParticipantMatchdayScore.total_points).label("min_points"),
            )
            .join(Matchday, ParticipantMatchdayScore.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
            )
            .group_by(Matchday.number)
            .order_by(Matchday.number.asc())
        )
        result = await self.session.execute(stmt)
        return [
            MatchdayAverageRow(
                matchday_number=int(row.matchday_number),
                avg_points=float(row.avg_points),
                max_points=int(row.max_points),
                min_points=int(row.min_points),
            )
            for row in result.all()
        ]
