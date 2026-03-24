"""Repository layer for advanced statistics queries.

Uses PostgreSQL aggregate functions (stddev_samp, percentile_cont) to compute
advanced metrics in SQL where possible.  The service layer adds Python-computed
metrics (confidence intervals, EWMA trend) on top.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Float, case, func, select, text
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

        # Most frequent position per player (mode)
        pos_mode = func.mode().within_group(PlayerStat.position)

        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.photo_path,
                pos_mode.label("position"),
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

    # ------------------------------------------------------------------
    # Phase 5 — Predictions / expected points
    # ------------------------------------------------------------------

    async def get_opponent_stats(self, season_id: int) -> dict[int, dict[str, float | str]]:
        """Goals conceded average and clean-sheet % per team for a season.

        Only counts completed matches (home_score IS NOT NULL) on counting
        matchdays.  Returns a dict keyed by team_id.
        """
        home_case = case(
            (Match.home_team_id == Team.id, Match.away_score),
            else_=Match.home_score,
        )
        cs_home = case(
            (Match.home_team_id == Team.id, case((Match.away_score == 0, 1), else_=None)),
            else_=None,
        )
        cs_away = case(
            (Match.away_team_id == Team.id, case((Match.home_score == 0, 1), else_=None)),
            else_=None,
        )
        clean_sheet_expr = func.coalesce(cs_home, cs_away)

        stmt = (
            select(
                Team.id.label("team_id"),
                Team.name.label("team_name"),
                func.avg(func.cast(home_case, Float)).label("goals_conceded_avg"),
                (
                    func.cast(func.count(clean_sheet_expr), Float)
                    / func.nullif(func.count(Match.id), 0)
                ).label("clean_sheet_pct"),
            )
            .join(
                Match,
                (Match.home_team_id == Team.id) | (Match.away_team_id == Team.id),
            )
            .join(Matchday, Match.matchday_id == Matchday.id)
            .where(
                Team.season_id == season_id,
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                Match.home_score.is_not(None),
            )
            .group_by(Team.id, Team.name)
        )

        result = await self.session.execute(stmt)
        out: dict[int, dict[str, float | str]] = {}
        for row in result.all():
            out[int(row.team_id)] = {
                "team_name": str(row.team_name),
                "goals_conceded_avg": float(row.goals_conceded_avg)
                if row.goals_conceded_avg is not None
                else 0.0,
                "clean_sheet_pct": float(row.clean_sheet_pct)
                if row.clean_sheet_pct is not None
                else 0.0,
            }
        return out

    async def get_fixtures_for_matchday(
        self, season_id: int, matchday_number: int
    ) -> list[dict[str, int | str]]:
        """Matches scheduled for a specific matchday (regardless of counts flag).

        Returns list of dicts with match info including team ids and names.
        """
        home_team = Team.__table__.alias("t1")
        away_team = Team.__table__.alias("t2")

        stmt = (
            select(
                Match.id.label("match_id"),
                Match.home_team_id,
                Match.away_team_id,
                home_team.c.name.label("home_name"),
                func.coalesce(home_team.c.short_name, home_team.c.name).label("home_short"),
                away_team.c.name.label("away_name"),
                func.coalesce(away_team.c.short_name, away_team.c.name).label("away_short"),
            )
            .join(Matchday, Match.matchday_id == Matchday.id)
            .join(home_team, Match.home_team_id == home_team.c.id)
            .join(away_team, Match.away_team_id == away_team.c.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.number == matchday_number,
            )
        )

        result = await self.session.execute(stmt)
        return [
            {
                "match_id": int(row.match_id),
                "home_team_id": int(row.home_team_id),
                "away_team_id": int(row.away_team_id),
                "home_name": str(row.home_name),
                "home_short": str(row.home_short),
                "away_name": str(row.away_name),
                "away_short": str(row.away_short),
            }
            for row in result.all()
        ]

    async def get_player_location_avgs(self, season_id: int) -> dict[int, dict[str, float]]:
        """Average fantasy points per player when playing home vs away.

        Uses player's current team_id to determine home/away from matches.
        Only counting matchdays and played stats are considered.
        """
        home_pts = case(
            (Match.home_team_id == Player.team_id, func.cast(PlayerStat.pts_total, Float)),
            else_=None,
        )
        away_pts = case(
            (Match.away_team_id == Player.team_id, func.cast(PlayerStat.pts_total, Float)),
            else_=None,
        )

        stmt = (
            select(
                PlayerStat.player_id,
                func.avg(home_pts).label("home_avg"),
                func.avg(away_pts).label("away_avg"),
            )
            .join(Player, PlayerStat.player_id == Player.id)
            .join(Match, PlayerStat.match_id == Match.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Player.season_id == season_id,
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .group_by(PlayerStat.player_id)
        )

        result = await self.session.execute(stmt)
        out: dict[int, dict[str, float]] = {}
        for row in result.all():
            out[int(row.player_id)] = {
                "home_avg": float(row.home_avg) if row.home_avg is not None else 0.0,
                "away_avg": float(row.away_avg) if row.away_avg is not None else 0.0,
            }
        return out

    async def get_player_season_stats_for_predictions(self, season_id: int) -> dict[int, dict]:
        """Per-player season aggregates needed for xPts calculation.

        Groups by player and most-common position (mode via window function
        on the raw stats).  Returns a dict keyed by player_id.
        """
        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.photo_path,
                Player.team_id,
                func.coalesce(Team.short_name, Team.name).label("team_name"),
                PlayerStat.position,
                func.count(PlayerStat.id).label("matchdays_played"),
                func.avg(func.cast(PlayerStat.pts_total, Float)).label("avg_pts"),
                func.coalesce(
                    func.stddev_samp(func.cast(PlayerStat.pts_total, Float)), text("0")
                ).label("std_dev"),
            )
            .join(Player, PlayerStat.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Player.season_id == season_id,
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .group_by(
                Player.id,
                Player.display_name,
                Player.photo_path,
                Player.team_id,
                Team.short_name,
                Team.name,
                PlayerStat.position,
            )
        )

        result = await self.session.execute(stmt)
        out: dict[int, dict] = {}
        for row in result.all():
            pid = int(row.player_id)
            # If a player appears under multiple positions keep highest avg_pts
            if pid not in out or float(row.avg_pts) > out[pid]["avg_pts"]:
                out[pid] = {
                    "player_name": str(row.display_name),
                    "photo_path": row.photo_path,
                    "team_id": int(row.team_id),
                    "team_name": str(row.team_name),
                    "position": str(row.position),
                    "matchdays_played": int(row.matchdays_played),
                    "avg_pts": float(row.avg_pts),
                    "std_dev": float(row.std_dev) if row.std_dev is not None else 0.0,
                }
        return out

    async def get_player_recent_points(self, season_id: int, n: int = 5) -> dict[int, list[float]]:
        """Last N matchday pts_total per player, ordered oldest to newest.

        Returns a dict keyed by player_id containing a list of floats.
        """
        # Rank matchdays per player in descending order so we can LIMIT to n
        ranked = (
            select(
                PlayerStat.player_id,
                PlayerStat.pts_total,
                Matchday.number.label("md_number"),
                func.row_number()
                .over(
                    partition_by=PlayerStat.player_id,
                    order_by=Matchday.number.desc(),
                )
                .label("rn"),
            )
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .join(Player, PlayerStat.player_id == Player.id)
            .where(
                Player.season_id == season_id,
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .subquery()
        )

        stmt = (
            select(
                ranked.c.player_id,
                ranked.c.pts_total,
                ranked.c.md_number,
            )
            .where(ranked.c.rn <= n)
            .order_by(ranked.c.player_id, ranked.c.md_number)
        )

        result = await self.session.execute(stmt)
        out: dict[int, list[float]] = {}
        for row in result.all():
            pid = int(row.player_id)
            if pid not in out:
                out[pid] = []
            out[pid].append(float(row.pts_total))
        return out

    async def get_player_starter_pct(self, season_id: int, n: int = 5) -> dict[int, float]:
        """% of last N matchdays where the player started (minutes >= 45).

        Returns dict of player_id -> starter percentage (0.0 to 1.0).
        """
        ranked = (
            select(
                PlayerStat.player_id,
                PlayerStat.minutes_played,
                func.row_number()
                .over(
                    partition_by=PlayerStat.player_id,
                    order_by=Matchday.number.desc(),
                )
                .label("rn"),
            )
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .join(Player, PlayerStat.player_id == Player.id)
            .where(
                Player.season_id == season_id,
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.played.is_(True),
            )
            .subquery()
        )

        stmt = (
            select(
                ranked.c.player_id,
                func.count().label("total"),
                func.sum(case((ranked.c.minutes_played >= 45, 1), else_=0)).label("starts"),
            )
            .where(ranked.c.rn <= n)
            .group_by(ranked.c.player_id)
        )

        result = await self.session.execute(stmt)
        return {
            int(row.player_id): int(row.starts) / int(row.total)
            for row in result.all()
            if int(row.total) > 0
        }

    async def get_penalty_takers(self, season_id: int) -> set[int]:
        """Player IDs that have scored at least 1 penalty goal this season."""
        stmt = (
            select(PlayerStat.player_id)
            .join(Player, PlayerStat.player_id == Player.id)
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(
                Player.season_id == season_id,
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                PlayerStat.penalty_goals > 0,
            )
            .group_by(PlayerStat.player_id)
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def get_opponent_recent_stats(
        self, season_id: int, n: int = 5
    ) -> dict[int, dict[str, float]]:
        """Goals conceded avg per team using only the last N matches.

        Returns dict of team_id -> {goals_conceded_avg, matches}.
        """
        # Rank matches per team by matchday number desc
        home_ranked = (
            select(
                Match.home_team_id.label("team_id"),
                Match.away_score.label("goals_conceded"),
                func.row_number()
                .over(
                    partition_by=Match.home_team_id,
                    order_by=Matchday.number.desc(),
                )
                .label("rn"),
            )
            .join(Matchday, Match.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                Match.home_score.is_not(None),
            )
            .subquery()
        )
        away_ranked = (
            select(
                Match.away_team_id.label("team_id"),
                Match.home_score.label("goals_conceded"),
                func.row_number()
                .over(
                    partition_by=Match.away_team_id,
                    order_by=Matchday.number.desc(),
                )
                .label("rn"),
            )
            .join(Matchday, Match.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                Match.home_score.is_not(None),
            )
            .subquery()
        )

        # Union last N home + away, then avg per team
        from sqlalchemy import union_all

        combined = union_all(
            select(
                home_ranked.c.team_id,
                home_ranked.c.goals_conceded,
            ).where(home_ranked.c.rn <= n),
            select(
                away_ranked.c.team_id,
                away_ranked.c.goals_conceded,
            ).where(away_ranked.c.rn <= n),
        ).subquery()

        stmt = select(
            combined.c.team_id,
            func.avg(func.cast(combined.c.goals_conceded, Float)).label("goals_conceded_avg"),
            func.count().label("matches"),
        ).group_by(combined.c.team_id)

        result = await self.session.execute(stmt)
        return {
            int(row.team_id): {
                "goals_conceded_avg": float(row.goals_conceded_avg)
                if row.goals_conceded_avg
                else 0.0,
                "matches": int(row.matches),
            }
            for row in result.all()
        }
