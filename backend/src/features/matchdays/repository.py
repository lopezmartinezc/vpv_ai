from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_ownership_log import PlayerOwnershipLog
from src.shared.models.player_stat import PlayerStat
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.team import Team
from src.shared.models.user import User


@dataclass
class MatchdaySummaryRow:
    number: int
    status: str
    counts: bool
    stats_ok: bool
    first_match_at: datetime | None


@dataclass
class MatchRow:
    id: int
    home_team_name: str
    away_team_name: str
    home_score: int | None
    away_score: int | None
    counts: bool
    stats_ok: bool
    played_at: datetime | None


@dataclass
class ParticipantScoreRow:
    rank: int | None
    participant_id: int
    display_name: str
    total_points: int
    formation: str | None
    pending_players: int = 0


@dataclass
class LineupPlayerRow:
    display_order: int
    position_slot: str
    player_id: int
    player_name: str
    photo_path: str | None
    team_name: str
    points: int
    pts_play: int | None
    pts_starter: int | None
    pts_result: int | None
    pts_clean_sheet: int | None
    pts_goals: int | None
    pts_assists: int | None
    pts_yellow: int | None
    pts_red: int | None
    pts_marca: int | None
    pts_as: int | None
    pts_total: int | None


@dataclass
class BenchPlayerRow:
    player_id: int
    player_name: str
    photo_path: str | None
    position: str
    team_name: str
    matchday_points: int
    pts_play: int | None
    pts_starter: int | None
    pts_result: int | None
    pts_clean_sheet: int | None
    pts_goals: int | None
    pts_assists: int | None
    pts_yellow: int | None
    pts_red: int | None
    pts_marca: int | None
    pts_as: int | None
    pts_total: int | None


class MatchdayRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_season(
        self,
        season_id: int,
        *,
        stats_ok_only: bool = True,
    ) -> list[MatchdaySummaryRow]:
        stmt = select(
            Matchday.number,
            Matchday.status,
            Matchday.counts,
            Matchday.stats_ok,
            Matchday.first_match_at,
        ).where(Matchday.season_id == season_id)
        if stats_ok_only:
            stmt = stmt.where(Matchday.stats_ok.is_(True))
        stmt = stmt.order_by(Matchday.number.asc())

        result = await self.session.execute(stmt)
        return [
            MatchdaySummaryRow(
                number=row.number,
                status=row.status,
                counts=row.counts,
                stats_ok=row.stats_ok,
                first_match_at=row.first_match_at,
            )
            for row in result.all()
        ]

    async def get_matchday(
        self,
        season_id: int,
        number: int,
    ) -> Matchday | None:
        stmt = select(Matchday).where(
            Matchday.season_id == season_id,
            Matchday.number == number,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_matches(self, matchday_id: int) -> list[MatchRow]:
        home_team = aliased(Team)
        away_team = aliased(Team)
        stmt = (
            select(
                Match.id,
                home_team.name.label("home_team_name"),
                away_team.name.label("away_team_name"),
                Match.home_score,
                Match.away_score,
                Match.counts,
                Match.stats_ok,
                Match.played_at,
            )
            .join(home_team, Match.home_team_id == home_team.id)
            .join(away_team, Match.away_team_id == away_team.id)
            .where(Match.matchday_id == matchday_id)
            .order_by(Match.played_at.asc().nulls_last())
        )
        result = await self.session.execute(stmt)
        return [
            MatchRow(
                id=row.id,
                home_team_name=row.home_team_name,
                away_team_name=row.away_team_name,
                home_score=row.home_score,
                away_score=row.away_score,
                counts=row.counts,
                stats_ok=row.stats_ok,
                played_at=row.played_at,
            )
            for row in result.all()
        ]

    async def get_scores(self, matchday_id: int) -> list[ParticipantScoreRow]:
        # Subquery: count lineup players whose team's match is not stats_ok
        # A player is "pending" when their team plays in a match without stats yet
        pending_sub = (
            select(
                Lineup.participant_id,
                func.count(LineupPlayer.id).label("pending"),
            )
            .join(LineupPlayer, LineupPlayer.lineup_id == Lineup.id)
            .join(Player, Player.id == LineupPlayer.player_id)
            .join(
                Match,
                and_(
                    Match.matchday_id == matchday_id,
                    Match.counts.is_(True),
                    Match.stats_ok.is_(False),
                    (Player.team_id == Match.home_team_id)
                    | (Player.team_id == Match.away_team_id),
                ),
            )
            .where(Lineup.matchday_id == matchday_id)
            .group_by(Lineup.participant_id)
            .subquery()
        )

        stmt = (
            select(
                ParticipantMatchdayScore.ranking.label("rank"),
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                ParticipantMatchdayScore.total_points,
                Lineup.formation,
                func.coalesce(pending_sub.c.pending, 0).label("pending_players"),
            )
            .join(
                SeasonParticipant,
                ParticipantMatchdayScore.participant_id == SeasonParticipant.id,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .outerjoin(
                Lineup,
                and_(
                    Lineup.participant_id == SeasonParticipant.id,
                    Lineup.matchday_id == matchday_id,
                ),
            )
            .outerjoin(
                pending_sub,
                pending_sub.c.participant_id == SeasonParticipant.id,
            )
            .where(ParticipantMatchdayScore.matchday_id == matchday_id)
            .order_by(
                ParticipantMatchdayScore.ranking.asc().nulls_last(),
            )
        )
        result = await self.session.execute(stmt)
        return [
            ParticipantScoreRow(
                rank=row.rank,
                participant_id=row.participant_id,
                display_name=row.display_name,
                total_points=row.total_points,
                formation=row.formation,
                pending_players=row.pending_players,
            )
            for row in result.all()
        ]

    async def get_lineup(
        self,
        matchday_id: int,
        participant_id: int,
    ) -> Lineup | None:
        stmt = select(Lineup).where(
            Lineup.matchday_id == matchday_id,
            Lineup.participant_id == participant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_lineup_players(
        self,
        lineup_id: int,
        matchday_id: int,
    ) -> list[LineupPlayerRow]:
        stmt = (
            select(
                LineupPlayer.display_order,
                LineupPlayer.position_slot,
                Player.id.label("player_id"),
                Player.display_name.label("player_name"),
                Player.photo_path,
                func.coalesce(Team.short_name, Team.name).label("team_name"),
                LineupPlayer.points,
                PlayerStat.pts_play,
                PlayerStat.pts_starter,
                PlayerStat.pts_result,
                PlayerStat.pts_clean_sheet,
                PlayerStat.pts_goals,
                PlayerStat.pts_assists,
                PlayerStat.pts_yellow,
                PlayerStat.pts_red,
                PlayerStat.pts_marca,
                PlayerStat.pts_as,
                PlayerStat.pts_total,
            )
            .join(Player, LineupPlayer.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .outerjoin(
                PlayerStat,
                and_(
                    PlayerStat.player_id == Player.id,
                    PlayerStat.matchday_id == matchday_id,
                ),
            )
            .where(LineupPlayer.lineup_id == lineup_id)
            .order_by(LineupPlayer.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return [
            LineupPlayerRow(
                display_order=row.display_order,
                position_slot=row.position_slot,
                player_id=row.player_id,
                player_name=row.player_name,
                photo_path=row.photo_path,
                team_name=row.team_name,
                points=row.points,
                pts_play=row.pts_play,
                pts_starter=row.pts_starter,
                pts_result=row.pts_result,
                pts_clean_sheet=row.pts_clean_sheet,
                pts_goals=row.pts_goals,
                pts_assists=row.pts_assists,
                pts_yellow=row.pts_yellow,
                pts_red=row.pts_red,
                pts_marca=row.pts_marca,
                pts_as=row.pts_as,
                pts_total=row.pts_total,
            )
            for row in result.all()
        ]

    async def get_bench_players(
        self,
        matchday_id: int,
        participant_id: int,
        season_id: int,
        lineup_player_ids: set[int],
        matchday_number: int | None = None,
    ) -> list[BenchPlayerRow]:
        """Get squad players NOT in the lineup, with their matchday points.

        When matchday_number is provided, uses player_ownership_log for
        historical ownership instead of the current players.owner_id.
        """
        base = (
            select(
                Player.id.label("player_id"),
                Player.display_name.label("player_name"),
                Player.photo_path,
                Player.position,
                func.coalesce(Team.short_name, Team.name).label("team_name"),
                func.coalesce(PlayerStat.pts_total, 0).label("matchday_points"),
                PlayerStat.pts_play,
                PlayerStat.pts_starter,
                PlayerStat.pts_result,
                PlayerStat.pts_clean_sheet,
                PlayerStat.pts_goals,
                PlayerStat.pts_assists,
                PlayerStat.pts_yellow,
                PlayerStat.pts_red,
                PlayerStat.pts_marca,
                PlayerStat.pts_as,
                PlayerStat.pts_total,
            )
            .join(Team, Player.team_id == Team.id)
            .outerjoin(
                PlayerStat,
                and_(
                    PlayerStat.player_id == Player.id,
                    PlayerStat.matchday_id == matchday_id,
                ),
            )
        )

        if matchday_number is not None:
            # Historical ownership via ownership log
            row_num = (
                func.row_number()
                .over(
                    partition_by=PlayerOwnershipLog.player_id,
                    order_by=PlayerOwnershipLog.from_matchday.desc(),
                )
                .label("rn")
            )
            ownership = (
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
            owner_sub = (
                select(ownership.c.player_id)
                .where(
                    ownership.c.rn == 1,
                    ownership.c.participant_id == participant_id,
                )
                .subquery()
            )
            base = base.join(owner_sub, Player.id == owner_sub.c.player_id)
            base = base.where(
                Player.season_id == season_id,
                Player.id.not_in(lineup_player_ids) if lineup_player_ids else true(),
            )
        else:
            base = base.where(
                Player.season_id == season_id,
                Player.owner_id == participant_id,
                Player.id.not_in(lineup_player_ids) if lineup_player_ids else true(),
            )

        stmt = base.order_by(
            func.array_position(
                func.string_to_array("POR,DEF,MED,DEL", ","),
                Player.position,
            ).asc(),
            Player.display_name.asc(),
        )
        result = await self.session.execute(stmt)
        return [
            BenchPlayerRow(
                player_id=row.player_id,
                player_name=row.player_name,
                photo_path=row.photo_path,
                position=row.position,
                team_name=row.team_name,
                matchday_points=row.matchday_points,
                pts_play=row.pts_play,
                pts_starter=row.pts_starter,
                pts_result=row.pts_result,
                pts_clean_sheet=row.pts_clean_sheet,
                pts_goals=row.pts_goals,
                pts_assists=row.pts_assists,
                pts_yellow=row.pts_yellow,
                pts_red=row.pts_red,
                pts_marca=row.pts_marca,
                pts_as=row.pts_as,
                pts_total=row.pts_total,
            )
            for row in result.all()
        ]

    async def update_matchday(
        self,
        season_id: int,
        number: int,
        **kwargs: object,
    ) -> Matchday | None:
        matchday = await self.get_matchday(season_id, number)
        if matchday is None:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(matchday, key, value)
        return matchday

    async def update_match(
        self,
        match_id: int,
        **kwargs: object,
    ) -> Match | None:
        match = await self.session.get(Match, match_id)
        if match is None:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(match, key, value)
        return match
