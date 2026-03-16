"""Service layer for advanced statistics.

Combines SQL-computed aggregates from the repository with Python-computed
metrics: confidence intervals, EWMA trend, and points per 90 minutes.
"""

from __future__ import annotations

import math
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.stats.repository_advanced import (
    AdvancedPlayerRow,
    AdvancedStatsRepository,
    PlayerMatchdayPoints,
    PositionPlayerRow,
)
from src.features.stats.schemas_advanced import (
    AdvancedPlayerStat,
    AdvancedPlayersResponse,
    ComparePlayerAxis,
    ComparePlayersResponse,
    DraftHistoryResponse,
    PickValuePoint,
    PlayerSplit,
    PlayerSplitsResponse,
    PositionAnalysis,
    PositionRoundValue,
    PositionTier,
    PositionTierPlayer,
    PositionValueResponse,
    RateEntry,
    TeamDependencyEntry,
    TeamDependencyResponse,
)


# ---------------------------------------------------------------------------
# t-distribution critical values for 95% CI (two-tailed, alpha=0.025)
# Key = degrees of freedom (n - 1), value = t-critical
# Covers n = 2..38 (matchdays_played = 2..38)
# ---------------------------------------------------------------------------

_T_TABLE_95: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
    35: 2.030,
    37: 2.026,
}


def _t_critical(df: int) -> float:
    """Get t-critical value for given degrees of freedom.

    Uses exact table values where available, falls back to linear
    interpolation or the normal approximation (1.96) for large df.
    """
    if df in _T_TABLE_95:
        return _T_TABLE_95[df]
    if df > 37:
        return 1.96  # Normal approximation for large samples
    # Linear interpolation between nearest known values
    lower = max(k for k in _T_TABLE_95 if k < df)
    upper = min(k for k in _T_TABLE_95 if k > df)
    ratio = (df - lower) / (upper - lower)
    return _T_TABLE_95[lower] + ratio * (_T_TABLE_95[upper] - _T_TABLE_95[lower])


def _ewma(values: list[float], alpha: float = 0.3) -> float:
    """Exponentially Weighted Moving Average.

    More recent values get higher weight.  alpha=0.3 means:
    - Most recent: 30% weight
    - Second most recent: 21% weight (0.3 * 0.7)
    - Third: 14.7%, etc.
    """
    if not values:
        return 0.0
    result = values[0]
    for v in values[1:]:
        result = alpha * v + (1.0 - alpha) * result
    return result


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AdvancedStatsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AdvancedStatsRepository(session)

    async def get_advanced_players(
        self,
        season_id: int,
        min_played: int = 3,
        position: str | None = None,
    ) -> AdvancedPlayersResponse:
        """Build the full advanced player stats response.

        1. Fetch SQL aggregates (avg, stddev, percentiles)
        2. Fetch per-matchday points for EWMA
        3. Compute CI, pp90, form, trend in Python
        """
        # Run both queries
        rows = await self.repo.get_advanced_player_stats(
            season_id, min_played, position
        )
        md_points = await self.repo.get_player_matchday_points(
            season_id, min_played, position
        )

        # Group matchday points by player_id
        points_by_player: dict[int, list[float]] = defaultdict(list)
        for mp in md_points:
            points_by_player[mp.player_id].append(float(mp.pts_total))

        players: list[AdvancedPlayerStat] = []
        for row in rows:
            players.append(self._build_stat(row, points_by_player.get(row.player_id, [])))

        return AdvancedPlayersResponse(season_id=season_id, players=players)

    def _build_stat(
        self,
        row: AdvancedPlayerRow,
        matchday_pts: list[float],
    ) -> AdvancedPlayerStat:
        """Combine SQL row with Python-computed metrics."""
        n = row.matchdays_played
        avg = row.avg_points
        std = row.std_dev if row.std_dev is not None else 0.0

        # Coefficient of variation
        cv = std / avg if avg > 0 else 0.0

        # Points per 90 minutes
        pp90 = (
            (row.total_points / row.minutes_played) * 90.0
            if row.minutes_played > 0
            else 0.0
        )

        # 95% confidence interval
        if n >= 2 and std > 0:
            t = _t_critical(n - 1)
            margin = t * (std / math.sqrt(n))
            ci_lower = avg - margin
            ci_upper = avg + margin
        else:
            ci_lower = avg
            ci_upper = avg

        # Form (EWMA of last 5 matchdays)
        form_5: float | None = None
        if len(matchday_pts) >= 5:
            form_5 = round(_ewma(matchday_pts[-5:]), 2)

        # Trend: compare form to season average
        if form_5 is not None and avg > 0:
            if form_5 > avg * 1.1:
                trend = "rising"
            elif form_5 < avg * 0.9:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return AdvancedPlayerStat(
            player_id=row.player_id,
            display_name=row.display_name,
            photo_path=row.photo_path,
            position=row.position,
            team_name=row.team_name,
            matchdays_played=n,
            minutes_played=row.minutes_played,
            total_points=row.total_points,
            avg_points=round(avg, 2),
            std_dev=round(std, 2),
            cv=round(cv, 2),
            p10=round(row.p10, 1),
            p50=round(row.p50, 1),
            p90=round(row.p90, 1),
            pp90=round(pp90, 2),
            ci_lower=round(ci_lower, 2),
            ci_upper=round(ci_upper, 2),
            form_5=form_5,
            trend=trend,
        )

    # ------------------------------------------------------------------
    # Phase 2 — Position value analysis
    # ------------------------------------------------------------------

    # Typical number of players drafted per position (11 participants × 26 players)
    # POR: ~3-4 per participant → ~33-44 total drafted
    # DEF: ~8-9 → ~88-99
    # MED: ~8-9 → ~88-99
    # DEL: ~6-7 → ~66-77
    # Replacement level = (N+1)th player, where N = typical drafted count
    _TYPICAL_DRAFTED: dict[str, int] = {"POR": 35, "DEF": 90, "MED": 90, "DEL": 70}

    async def get_position_value(
        self, season_id: int, min_played: int = 3
    ) -> PositionValueResponse:
        """Compute position analysis: replacement level, PAR, tiers."""
        rows = await self.repo.get_position_totals(season_id, min_played)

        # Group by position
        by_pos: dict[str, list[PositionPlayerRow]] = defaultdict(list)
        for row in rows:
            by_pos[row.position].append(row)

        positions: list[PositionAnalysis] = []
        for pos in ["POR", "DEF", "MED", "DEL"]:
            players = by_pos.get(pos, [])
            if not players:
                continue

            # Already sorted by total_points desc from SQL
            totals = [p.total_points for p in players]
            n = len(totals)

            # Replacement level
            draft_n = self._TYPICAL_DRAFTED.get(pos, n)
            repl_idx = min(draft_n, n - 1)
            replacement_level = float(totals[repl_idx]) if repl_idx < n else 0.0

            avg_pts = sum(totals) / n
            median_pts = float(totals[n // 2])

            # Tiers via quartile breakpoints
            tiers = self._compute_tiers(players, totals, replacement_level)

            # Scarcity = ratio of tier-1 (elite) players to total
            elite_count = len(tiers[0].players) if tiers else 0
            scarcity = elite_count / n if n > 0 else 0.0

            positions.append(
                PositionAnalysis(
                    position=pos,
                    player_count=n,
                    replacement_level=replacement_level,
                    avg_points=round(avg_pts, 1),
                    median_points=median_pts,
                    scarcity_index=round(scarcity, 3),
                    tiers=tiers,
                )
            )

        return PositionValueResponse(season_id=season_id, positions=positions)

    @staticmethod
    def _compute_tiers(
        players: list[PositionPlayerRow],
        totals: list[int],
        replacement_level: float,
    ) -> list[PositionTier]:
        """Split players into 4 tiers using percentile breakpoints."""
        n = len(totals)
        if n == 0:
            return []

        # Breakpoints at 90th, 75th, 50th percentile
        p90_idx = max(0, int(n * 0.10))  # top 10%
        p75_idx = max(0, int(n * 0.25))  # top 25%
        p50_idx = max(0, int(n * 0.50))  # top 50%

        cuts = [
            (1, "Elite", 0, p90_idx),
            (2, "Solido", p90_idx, p75_idx),
            (3, "Promedio", p75_idx, p50_idx),
            (4, "Reemplazable", p50_idx, n),
        ]

        tiers: list[PositionTier] = []
        for tier_num, label, start, end in cuts:
            tier_players = players[start:end]
            if not tier_players:
                continue
            tier_totals = totals[start:end]
            tiers.append(
                PositionTier(
                    tier=tier_num,
                    label=label,
                    min_points=float(min(tier_totals)),
                    max_points=float(max(tier_totals)),
                    players=[
                        PositionTierPlayer(
                            player_id=p.player_id,
                            display_name=p.display_name,
                            team_name=p.team_name,
                            total_points=p.total_points,
                            par=round(p.total_points - replacement_level, 1),
                        )
                        for p in tier_players
                    ],
                )
            )

        return tiers

    # ------------------------------------------------------------------
    # Phase 3 — Draft history
    # ------------------------------------------------------------------

    async def get_draft_history(
        self, season_ids: list[int] | None = None
    ) -> DraftHistoryResponse:
        """Compute draft analytics: pick value curve, bust/steal rates."""
        pick_values = await self.repo.get_draft_pick_values(season_ids)
        pos_by_round = await self.repo.get_draft_position_by_round(season_ids)
        pick_details = await self.repo.get_draft_pick_details(season_ids)

        # Bust/steal rates
        bust_rate = self._compute_bust_rate(pick_details)
        steal_rate = self._compute_steal_rate(pick_details)

        return DraftHistoryResponse(
            pick_value_curve=[
                PickValuePoint(
                    pick_number=pv.pick_number,
                    avg_total_points=pv.avg_total_points,
                    sample_count=pv.sample_count,
                )
                for pv in pick_values
            ],
            position_by_round=[
                PositionRoundValue(
                    round_number=pr.round_number,
                    position=pr.position,
                    avg_total_points=pr.avg_total_points,
                    pick_count=pr.pick_count,
                )
                for pr in pos_by_round
            ],
            bust_rate=bust_rate,
            steal_rate=steal_rate,
        )

    @staticmethod
    def _compute_bust_rate(
        picks: list,
    ) -> list[RateEntry]:
        """% of early round picks (1-3) that produce below-median points."""
        if not picks:
            return []

        all_points = [p.total_points for p in picks]
        if not all_points:
            return []
        median = sorted(all_points)[len(all_points) // 2]

        ranges = [("1-3", 1, 3), ("4-6", 4, 6)]
        result: list[RateEntry] = []
        for label, r_min, r_max in ranges:
            round_picks = [
                p for p in picks if r_min <= p.round_number <= r_max
            ]
            if not round_picks:
                continue
            busts = sum(1 for p in round_picks if p.total_points < median)
            result.append(
                RateEntry(
                    round_range=label,
                    rate_pct=round(busts / len(round_picks) * 100, 1),
                    total_picks=len(round_picks),
                )
            )
        return result

    @staticmethod
    def _compute_steal_rate(
        picks: list,
    ) -> list[RateEntry]:
        """% of late round picks that outperform early-round median."""
        if not picks:
            return []

        # Median of rounds 1-3 as the benchmark
        early = [p.total_points for p in picks if p.round_number <= 3]
        if not early:
            return []
        early_median = sorted(early)[len(early) // 2]

        ranges = [("20-26", 20, 26), ("15-19", 15, 19)]
        result: list[RateEntry] = []
        for label, r_min, r_max in ranges:
            round_picks = [
                p for p in picks if r_min <= p.round_number <= r_max
            ]
            if not round_picks:
                continue
            steals = sum(
                1 for p in round_picks if p.total_points > early_median
            )
            result.append(
                RateEntry(
                    round_range=label,
                    rate_pct=round(steals / len(round_picks) * 100, 1),
                    total_picks=len(round_picks),
                )
            )
        return result

    # ------------------------------------------------------------------
    # Phase 4 — Context analysis
    # ------------------------------------------------------------------

    async def get_player_splits(
        self, season_id: int, player_id: int
    ) -> PlayerSplitsResponse:
        """Home/away splits for a single player."""
        rows = await self.repo.get_player_splits(season_id, player_id)

        # Get player name from first row or fetch separately
        display_name = rows[0].location if not rows else ""
        # We need the player name — get it from the split rows context
        # Since splits don't carry the name, fetch from the advanced stats
        from src.shared.models.player import Player
        from sqlalchemy import select

        result = await self.repo.session.execute(
            select(Player.display_name).where(Player.id == player_id)
        )
        name_row = result.scalar_one_or_none()
        display_name = name_row or f"Player {player_id}"

        return PlayerSplitsResponse(
            player_id=player_id,
            display_name=display_name,
            season_id=season_id,
            splits=[
                PlayerSplit(
                    location=r.location,
                    matches=r.matches,
                    avg_points=r.avg_points,
                    total_points=r.total_points,
                    goals=r.goals,
                    assists=r.assists,
                )
                for r in rows
            ],
        )

    async def get_team_dependency(
        self, season_id: int, min_played: int = 3
    ) -> TeamDependencyResponse:
        """Team dependency: how much each team relies on one player."""
        rows = await self.repo.get_team_dependency(season_id, min_played)
        return TeamDependencyResponse(
            season_id=season_id,
            entries=[
                TeamDependencyEntry(
                    team_name=r.team_name,
                    top_player_name=r.top_player_name,
                    top_player_id=r.top_player_id,
                    top_player_points=r.top_player_points,
                    team_total_points=r.team_total,
                    dependency_pct=round(
                        r.top_player_points / r.team_total * 100, 1
                    )
                    if r.team_total > 0
                    else 0.0,
                )
                for r in rows
            ],
        )

    async def get_compare_players(
        self, season_id: int, player_ids: list[int]
    ) -> ComparePlayersResponse:
        """Radar chart comparison: normalize 6 axes to 0-100."""
        rows = await self.repo.get_compare_raw(season_id, player_ids)

        if not rows:
            return ComparePlayersResponse(season_id=season_id, players=[])

        # Also need form_5 — fetch matchday points for these players
        md_points = await self.repo.get_player_matchday_points(
            season_id, min_played=1
        )
        points_by_player: dict[int, list[float]] = defaultdict(list)
        for mp in md_points:
            if mp.player_id in player_ids:
                points_by_player[mp.player_id].append(float(mp.pts_total))

        # Compute raw values
        raw: list[dict] = []
        for r in rows:
            n = r.matchdays_played
            goals_rate = r.goals / n if n > 0 else 0
            assists_rate = r.assists / n if n > 0 else 0
            cv = r.std_dev / r.avg_points if r.avg_points > 0 else 1.0
            consistency = max(0.0, 1.0 - cv)
            pp90 = (r.total_points / r.minutes_played) * 90 if r.minutes_played > 0 else 0
            pts = points_by_player.get(r.player_id, [])
            form = _ewma(pts[-5:]) if len(pts) >= 5 else r.avg_points

            raw.append({
                "row": r,
                "goals_rate": goals_rate,
                "assists_rate": assists_rate,
                "avg_points": r.avg_points,
                "consistency": consistency,
                "pp90": pp90,
                "form": form,
            })

        # Find max for each axis to normalize 0-100
        axes = ["goals_rate", "assists_rate", "avg_points", "consistency", "pp90", "form"]
        maxes = {ax: max((d[ax] for d in raw), default=1) or 1 for ax in axes}

        players = []
        for d in raw:
            r = d["row"]
            players.append(
                ComparePlayerAxis(
                    player_id=r.player_id,
                    display_name=r.display_name,
                    photo_path=r.photo_path,
                    position=r.position,
                    team_name=r.team_name,
                    goals_rate=round(d["goals_rate"] / maxes["goals_rate"] * 100, 1),
                    assists_rate=round(d["assists_rate"] / maxes["assists_rate"] * 100, 1),
                    avg_points=round(d["avg_points"] / maxes["avg_points"] * 100, 1),
                    consistency=round(d["consistency"] / maxes["consistency"] * 100, 1),
                    pp90=round(d["pp90"] / maxes["pp90"] * 100, 1),
                    form=round(d["form"] / maxes["form"] * 100, 1),
                )
            )

        return ComparePlayersResponse(season_id=season_id, players=players)
