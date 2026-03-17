"""Repository layer for advanced statistics queries.

Uses PostgreSQL aggregate functions (stddev_samp, percentile_cont) to compute
advanced metrics in SQL where possible.  The service layer adds Python-computed
metrics (confidence intervals, EWMA trend) on top.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Float, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.draft import Draft, DraftPick
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.team import Team

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AdvancedPlayerRow:
    """SQL-computed advanced metrics for a single player."""

    player_id: int
    display_name: str
    photo_path: str | None
    position: str
    team_name: str
    matchdays_played: int
    minutes_played: int
    total_points: int
    avg_points: float
    std_dev: float | None  # None when only 1 matchday (stddev_samp undefined)
    p10: float
    p50: float
    p90: float


@dataclass
class PositionPlayerRow:
    """Per-player total points for position analysis."""

    player_id: int
    display_name: str
    team_name: str
    position: str
    total_points: int


@dataclass
class DraftPickValueRow:
    """Aggregated draft pick value across seasons."""

    pick_number: int
    avg_total_points: float
    sample_count: int


@dataclass
class DraftPositionRoundRow:
    """Average points by position and round across seasons."""

    round_number: int
    position: str
    avg_total_points: float
    pick_count: int


@dataclass
class DraftPickDetailRow:
    """Individual draft pick with season points for bust/steal analysis."""

    pick_number: int
    round_number: int
    position: str
    total_points: int


@dataclass
class PlayerSplitRow:
    """Home/away split for a single player."""

    location: str  # "home" | "away"
    matches: int
    avg_points: float
    total_points: int
    goals: int
    assists: int


@dataclass
class TeamDependencyRow:
    """Top player and team total for dependency analysis."""

    team_name: str
    top_player_name: str
    top_player_id: int
    top_player_points: int
    team_total: int


@dataclass
class CompareRawRow:
    """Raw stats for radar chart normalization."""

    player_id: int
    display_name: str
    photo_path: str | None
    position: str
    team_name: str
    matchdays_played: int
    minutes_played: int
    total_points: int
    avg_points: float
    std_dev: float
    goals: int
    assists: int


@dataclass
class PlayerMatchdayPoints:
    """A single matchday's points for a player — used for EWMA trend."""

    player_id: int
    matchday_number: int
    pts_total: int


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class AdvancedStatsRepository:
    """Read-only repository for advanced player statistics.

    Queries only consider matchdays where counts=True and player_stats
    where played=True.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_advanced_player_stats(
        self,
        season_id: int,
        min_played: int = 3,
        position: str | None = None,
    ) -> list[AdvancedPlayerRow]:
        """Aggregate per-player stats with stddev and percentiles.

        Uses PostgreSQL ordered-set aggregates (percentile_cont) and
        stddev_samp for dispersion.
        """
        total_pts = func.coalesce(func.sum(PlayerStat.pts_total), 0)
        md_count = func.count(PlayerStat.id)

        # PostgreSQL percentile_cont — ordered-set aggregate
        # SQLAlchemy doesn't have a built-in wrapper, so we use func + within_group
        p10 = func.percentile_cont(0.10).within_group(PlayerStat.pts_total)
        p50 = func.percentile_cont(0.50).within_group(PlayerStat.pts_total)
        p90 = func.percentile_cont(0.90).within_group(PlayerStat.pts_total)

        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.photo_path,
                PlayerStat.position,
                Team.name.label("team_name"),
                md_count.label("matchdays_played"),
                func.coalesce(func.sum(PlayerStat.minutes_played), 0).label("minutes_played"),
                total_pts.label("total_points"),
                func.avg(func.cast(PlayerStat.pts_total, Float)).label("avg_points"),
                func.stddev_samp(func.cast(PlayerStat.pts_total, Float)).label("std_dev"),
                p10.label("p10"),
                p50.label("p50"),
                p90.label("p90"),
            )
            .join(Player, PlayerStat.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
        )

        if position:
            stmt = stmt.where(PlayerStat.position == position)

        stmt = (
            stmt.group_by(
                Player.id,
                Player.display_name,
                Player.photo_path,
                PlayerStat.position,
                Team.name,
            )
            .having(md_count >= min_played)
            .order_by(total_pts.desc())
        )

        result = await self.session.execute(stmt)
        return [
            AdvancedPlayerRow(
                player_id=row.player_id,
                display_name=row.display_name,
                photo_path=row.photo_path,
                position=row.position,
                team_name=row.team_name,
                matchdays_played=int(row.matchdays_played),
                minutes_played=int(row.minutes_played),
                total_points=int(row.total_points),
                avg_points=float(row.avg_points),
                std_dev=float(row.std_dev) if row.std_dev is not None else None,
                p10=float(row.p10),
                p50=float(row.p50),
                p90=float(row.p90),
            )
            for row in result.all()
        ]

    async def get_player_matchday_points(
        self,
        season_id: int,
        min_played: int = 3,
        position: str | None = None,
    ) -> list[PlayerMatchdayPoints]:
        """Get per-matchday pts_total for each player, ordered by matchday.

        Used by the service layer to compute EWMA trend.  Only returns
        players with >= min_played matchdays (same filter as the main query).
        """
        # Subquery: player_ids that meet the min_played threshold
        qualifying = (
            select(PlayerStat.player_id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .join(Player, PlayerStat.player_id == Player.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
        )
        if position:
            qualifying = qualifying.where(PlayerStat.position == position)

        qualifying_sub = (
            qualifying.group_by(PlayerStat.player_id)
            .having(func.count(PlayerStat.id) >= min_played)
            .subquery()
        )

        stmt = (
            select(
                PlayerStat.player_id,
                Matchday.number.label("matchday_number"),
                PlayerStat.pts_total,
            )
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
                PlayerStat.player_id.in_(select(qualifying_sub.c.player_id)),
            )
            .order_by(PlayerStat.player_id, Matchday.number)
        )

        result = await self.session.execute(stmt)
        return [
            PlayerMatchdayPoints(
                player_id=row.player_id,
                matchday_number=row.matchday_number,
                pts_total=int(row.pts_total),
            )
            for row in result.all()
        ]

    # ------------------------------------------------------------------
    # Phase 2 — Position value analysis
    # ------------------------------------------------------------------

    async def get_position_totals(
        self, season_id: int, min_played: int = 3
    ) -> list[PositionPlayerRow]:
        """Per-player season totals grouped by position.

        Used by the service layer to compute replacement level, PAR, and tiers.
        """
        total_pts = func.coalesce(func.sum(PlayerStat.pts_total), 0)
        md_count = func.count(PlayerStat.id)

        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Team.name.label("team_name"),
                PlayerStat.position,
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
                Team.name,
                PlayerStat.position,
            )
            .having(md_count >= min_played)
            .order_by(PlayerStat.position, total_pts.desc())
        )

        result = await self.session.execute(stmt)
        return [
            PositionPlayerRow(
                player_id=row.player_id,
                display_name=row.display_name,
                team_name=row.team_name,
                position=row.position,
                total_points=int(row.total_points),
            )
            for row in result.all()
        ]

    # ------------------------------------------------------------------
    # Phase 3 — Draft history
    # ------------------------------------------------------------------

    async def get_draft_pick_values(
        self, season_ids: list[int] | None = None
    ) -> list[DraftPickValueRow]:
        """Average total season points per pick number across seasons.

        Only considers preseason drafts.
        """
        # Subquery: season total points per player
        season_pts = (
            select(
                Player.id.label("player_id"),
                Player.season_id,
                func.coalesce(func.sum(PlayerStat.pts_total), 0).label("total"),
            )
            .join(PlayerStat, PlayerStat.player_id == Player.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .group_by(Player.id, Player.season_id)
            .subquery()
        )

        stmt = (
            select(
                DraftPick.pick_number,
                func.avg(func.cast(season_pts.c.total, Float)).label("avg_total_points"),
                func.count().label("sample_count"),
            )
            .join(Draft, DraftPick.draft_id == Draft.id)
            .join(
                season_pts,
                DraftPick.player_id == season_pts.c.player_id,
            )
            .where(Draft.phase == "preseason")
        )

        if season_ids:
            stmt = stmt.where(Draft.season_id.in_(season_ids))

        stmt = stmt.group_by(DraftPick.pick_number).order_by(DraftPick.pick_number)

        result = await self.session.execute(stmt)
        return [
            DraftPickValueRow(
                pick_number=row.pick_number,
                avg_total_points=round(float(row.avg_total_points), 1),
                sample_count=int(row.sample_count),
            )
            for row in result.all()
        ]

    async def get_draft_position_by_round(
        self, season_ids: list[int] | None = None
    ) -> list[DraftPositionRoundRow]:
        """Average points by position and draft round."""
        season_pts = (
            select(
                Player.id.label("player_id"),
                func.coalesce(func.sum(PlayerStat.pts_total), 0).label("total"),
            )
            .join(PlayerStat, PlayerStat.player_id == Player.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .group_by(Player.id)
            .subquery()
        )

        stmt = (
            select(
                DraftPick.round_number,
                Player.position,
                func.avg(func.cast(season_pts.c.total, Float)).label("avg_total_points"),
                func.count().label("pick_count"),
            )
            .join(Draft, DraftPick.draft_id == Draft.id)
            .join(Player, DraftPick.player_id == Player.id)
            .join(season_pts, season_pts.c.player_id == Player.id)
            .where(Draft.phase == "preseason")
        )

        if season_ids:
            stmt = stmt.where(Draft.season_id.in_(season_ids))

        stmt = stmt.group_by(DraftPick.round_number, Player.position).order_by(
            DraftPick.round_number, Player.position
        )

        result = await self.session.execute(stmt)
        return [
            DraftPositionRoundRow(
                round_number=row.round_number,
                position=row.position,
                avg_total_points=round(float(row.avg_total_points), 1),
                pick_count=int(row.pick_count),
            )
            for row in result.all()
        ]

    async def get_draft_pick_details(
        self, season_ids: list[int] | None = None
    ) -> list[DraftPickDetailRow]:
        """Individual draft picks with season totals for bust/steal analysis."""
        season_pts = (
            select(
                Player.id.label("player_id"),
                func.coalesce(func.sum(PlayerStat.pts_total), 0).label("total"),
            )
            .join(PlayerStat, PlayerStat.player_id == Player.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .group_by(Player.id)
            .subquery()
        )

        stmt = (
            select(
                DraftPick.pick_number,
                DraftPick.round_number,
                Player.position,
                season_pts.c.total.label("total_points"),
            )
            .join(Draft, DraftPick.draft_id == Draft.id)
            .join(Player, DraftPick.player_id == Player.id)
            .join(season_pts, season_pts.c.player_id == Player.id)
            .where(Draft.phase == "preseason")
        )

        if season_ids:
            stmt = stmt.where(Draft.season_id.in_(season_ids))

        stmt = stmt.order_by(DraftPick.round_number, DraftPick.pick_number)

        result = await self.session.execute(stmt)
        return [
            DraftPickDetailRow(
                pick_number=row.pick_number,
                round_number=row.round_number,
                position=row.position,
                total_points=int(row.total_points),
            )
            for row in result.all()
        ]

    # ------------------------------------------------------------------
    # Phase 4 — Context analysis
    # ------------------------------------------------------------------

    async def get_player_splits(self, season_id: int, player_id: int) -> list[PlayerSplitRow]:
        """Home/away split stats for a single player in a season."""
        location = case(
            (Match.home_team_id == Player.team_id, "home"),
            else_="away",
        )

        stmt = (
            select(
                location.label("location"),
                func.count(PlayerStat.id).label("matches"),
                func.avg(func.cast(PlayerStat.pts_total, Float)).label("avg_points"),
                func.coalesce(func.sum(PlayerStat.pts_total), 0).label("total_points"),
                func.coalesce(func.sum(PlayerStat.goals), 0).label("goals"),
                func.coalesce(func.sum(PlayerStat.assists), 0).label("assists"),
            )
            .join(Player, PlayerStat.player_id == Player.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .join(Match, PlayerStat.match_id == Match.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
                PlayerStat.player_id == player_id,
            )
            .group_by(location)
            .order_by(location)
        )

        result = await self.session.execute(stmt)
        return [
            PlayerSplitRow(
                location=row.location,
                matches=int(row.matches),
                avg_points=round(float(row.avg_points), 2),
                total_points=int(row.total_points),
                goals=int(row.goals),
                assists=int(row.assists),
            )
            for row in result.all()
        ]

    async def get_team_dependency(
        self, season_id: int, min_played: int = 3
    ) -> list[TeamDependencyRow]:
        """Per-team: top scorer and their % of team total fantasy points."""
        # Subquery: per-player season total
        player_total = (
            select(
                PlayerStat.player_id,
                Player.display_name,
                Player.team_id,
                func.coalesce(func.sum(PlayerStat.pts_total), 0).label("total"),
            )
            .join(Player, PlayerStat.player_id == Player.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .group_by(PlayerStat.player_id, Player.display_name, Player.team_id)
            .having(func.count(PlayerStat.id) >= min_played)
            .subquery()
        )

        # Team total
        team_total = (
            select(
                player_total.c.team_id,
                func.sum(player_total.c.total).label("team_total"),
            )
            .group_by(player_total.c.team_id)
            .subquery()
        )

        # Top player per team (window function)
        ranked = select(
            player_total.c.player_id,
            player_total.c.display_name,
            player_total.c.team_id,
            player_total.c.total,
            func.row_number()
            .over(
                partition_by=player_total.c.team_id,
                order_by=player_total.c.total.desc(),
            )
            .label("rn"),
        ).subquery()

        stmt = (
            select(
                Team.name.label("team_name"),
                ranked.c.display_name.label("top_player_name"),
                ranked.c.player_id.label("top_player_id"),
                ranked.c.total.label("top_player_points"),
                team_total.c.team_total,
            )
            .join(Team, ranked.c.team_id == Team.id)
            .join(team_total, ranked.c.team_id == team_total.c.team_id)
            .where(ranked.c.rn == 1)
            .order_by(
                (
                    func.cast(ranked.c.total, Float) / func.cast(team_total.c.team_total, Float)
                ).desc()
            )
        )

        result = await self.session.execute(stmt)
        return [
            TeamDependencyRow(
                team_name=row.team_name,
                top_player_name=row.top_player_name,
                top_player_id=int(row.top_player_id),
                top_player_points=int(row.top_player_points),
                team_total=int(row.team_total),
            )
            for row in result.all()
        ]

    async def get_compare_raw(
        self, season_id: int, player_ids: list[int], min_played: int = 3
    ) -> list[CompareRawRow]:
        """Raw stats for player comparison radar chart."""
        md_count = func.count(PlayerStat.id)
        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.photo_path,
                PlayerStat.position,
                Team.name.label("team_name"),
                md_count.label("matchdays_played"),
                func.coalesce(func.sum(PlayerStat.minutes_played), 0).label("minutes_played"),
                func.coalesce(func.sum(PlayerStat.pts_total), 0).label("total_points"),
                func.avg(func.cast(PlayerStat.pts_total, Float)).label("avg_points"),
                func.stddev_samp(func.cast(PlayerStat.pts_total, Float)).label("std_dev"),
                func.coalesce(func.sum(PlayerStat.goals), 0).label("goals"),
                func.coalesce(func.sum(PlayerStat.assists), 0).label("assists"),
            )
            .join(Player, PlayerStat.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
                Player.id.in_(player_ids),
            )
            .group_by(
                Player.id,
                Player.display_name,
                Player.photo_path,
                PlayerStat.position,
                Team.name,
            )
            .having(md_count >= min_played)
        )

        result = await self.session.execute(stmt)
        return [
            CompareRawRow(
                player_id=row.player_id,
                display_name=row.display_name,
                photo_path=row.photo_path,
                position=row.position,
                team_name=row.team_name,
                matchdays_played=int(row.matchdays_played),
                minutes_played=int(row.minutes_played),
                total_points=int(row.total_points),
                avg_points=float(row.avg_points),
                std_dev=float(row.std_dev) if row.std_dev is not None else 0.0,
                goals=int(row.goals),
                assists=int(row.assists),
            )
            for row in result.all()
        ]
