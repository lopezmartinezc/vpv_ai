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
    PositionPlayerRow,
)
from src.features.stats.schemas_advanced import (
    AdvancedPlayersResponse,
    AdvancedPlayerStat,
    ComparePlayerAxis,
    ComparePlayersResponse,
    DraftHistoryResponse,
    OpponentDifficulty,
    PickValuePoint,
    PlayerPrediction,
    PlayerSplit,
    PlayerSplitsResponse,
    PositionAnalysis,
    PositionRoundValue,
    PositionTier,
    PositionTierPlayer,
    PositionValueResponse,
    PredictionsResponse,
    RateEntry,
    TeamDependencyEntry,
    TeamDependencyResponse,
)
from src.features.stats.scorecard import REPLACEMENT_RANK

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


# Bounds for the xPts rival factor. A modest schedule nudge — not a swing that
# can 10x a player's expected points off a small-sample opponent stat.
_RIVAL_FACTOR_MIN = 0.7
_RIVAL_FACTOR_MAX = 1.4


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
        include_noncounting: bool = False,
    ) -> AdvancedPlayersResponse:
        """Build the full advanced player stats response.

        1. Fetch SQL aggregates (avg, stddev, percentiles)
        2. Fetch per-matchday points for EWMA
        3. Compute CI, pp90, form, trend in Python
        """
        # Pre-draft preview: only 1-2 matchdays exist, so the usual min_played=3
        # floor would exclude everyone. Drop it to 1 when non-counting is on.
        if include_noncounting:
            min_played = 1
        # Run both queries
        rows = await self.repo.get_advanced_player_stats(
            season_id, min_played, position, include_noncounting
        )
        md_points = await self.repo.get_player_matchday_points(
            season_id, min_played, position, include_noncounting
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
        pp90 = (row.total_points / row.minutes_played) * 90.0 if row.minutes_played > 0 else 0.0

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
            draft_n = REPLACEMENT_RANK.get(pos, n)
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

    async def get_draft_history(self, season_ids: list[int] | None = None) -> DraftHistoryResponse:
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
            round_picks = [p for p in picks if r_min <= p.round_number <= r_max]
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
            round_picks = [p for p in picks if r_min <= p.round_number <= r_max]
            if not round_picks:
                continue
            steals = sum(1 for p in round_picks if p.total_points > early_median)
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
        self, season_id: int, player_id: int, include_noncounting: bool = False
    ) -> PlayerSplitsResponse:
        """Home/away splits for a single player."""
        rows = await self.repo.get_player_splits(season_id, player_id, include_noncounting)

        # Splits don't carry the name — fetch it (falls back for empty splits).
        from sqlalchemy import select

        from src.shared.models.player import Player

        result = await self.repo.session.execute(
            select(Player.display_name).where(Player.id == player_id)
        )
        display_name = result.scalar_one_or_none() or f"Player {player_id}"

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
        self, season_id: int, min_played: int = 3, include_noncounting: bool = False
    ) -> TeamDependencyResponse:
        """Team dependency: how much each team relies on one player."""
        if include_noncounting:
            min_played = 1
        rows = await self.repo.get_team_dependency(season_id, min_played, include_noncounting)
        return TeamDependencyResponse(
            season_id=season_id,
            entries=[
                TeamDependencyEntry(
                    team_name=r.team_name,
                    top_player_name=r.top_player_name,
                    top_player_id=r.top_player_id,
                    top_player_points=r.top_player_points,
                    team_total_points=r.team_total,
                    dependency_pct=round(r.top_player_points / r.team_total * 100, 1)
                    if r.team_total > 0
                    else 0.0,
                )
                for r in rows
            ],
        )

    async def get_compare_players(
        self, season_id: int, player_ids: list[int], include_noncounting: bool = False
    ) -> ComparePlayersResponse:
        """Radar chart comparison: normalize 6 axes to 0-100."""
        rows = await self.repo.get_compare_raw(
            season_id,
            player_ids,
            min_played=1 if include_noncounting else 3,
            include_noncounting=include_noncounting,
        )

        if not rows:
            return ComparePlayersResponse(season_id=season_id, players=[])

        # Also need form_5 — fetch matchday points for these players
        md_points = await self.repo.get_player_matchday_points(season_id, min_played=1)
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

            raw.append(
                {
                    "row": r,
                    "goals_rate": goals_rate,
                    "assists_rate": assists_rate,
                    "avg_points": r.avg_points,
                    "consistency": consistency,
                    "pp90": pp90,
                    "form": form,
                }
            )

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

    # ------------------------------------------------------------------
    # Phase 5 — Predictions / expected points
    # ------------------------------------------------------------------

    async def get_predictions(self, season_id: int, matchday_number: int) -> PredictionsResponse:
        """Calculate expected points (xPts) for all players with a fixture.

        Formula:
            xPts = (form_5 * 0.40) + (season_avg * 0.20)
                   + (season_avg * rival_factor * 0.25) + (location_avg * 0.15)

        rival_factor for POR/DEF = league_avg_goals / opponent_goals_conceded_avg
        rival_factor for MED/DEL = opponent_goals_conceded_avg / league_avg_goals
        """
        # 1. Fixtures for the target matchday
        fixtures = await self.repo.get_fixtures_for_matchday(season_id, matchday_number)
        if not fixtures:
            return PredictionsResponse(
                season_id=season_id,
                matchday_number=matchday_number,
                predictions=[],
                opponent_rankings=[],
            )

        # 2. Build team_id -> fixture mapping (each team appears in exactly one match)
        team_fixture: dict[int, dict] = {}
        for fixture in fixtures:
            team_fixture[int(fixture["home_team_id"])] = fixture
            team_fixture[int(fixture["away_team_id"])] = fixture

        # 3. Season-level player aggregates
        player_stats = await self.repo.get_player_season_stats_for_predictions(season_id)

        # 4. Opponent defensive stats + league average
        opponent_stats = await self.repo.get_opponent_stats(season_id)
        if opponent_stats:
            league_avg_goals = sum(
                float(o["goals_conceded_avg"]) for o in opponent_stats.values()
            ) / len(opponent_stats)
        else:
            league_avg_goals = 1.0

        # 5. Location (home/away) averages per player
        location_avgs = await self.repo.get_player_location_avgs(season_id)

        # 6. Recent points for form calculation (last 5)
        recent_points = await self.repo.get_player_recent_points(season_id, n=5)

        # 7. Starter probability (last 5 matches)
        starter_pcts = await self.repo.get_player_starter_pct(season_id, n=5)

        # 8. Penalty takers
        penalty_takers = await self.repo.get_penalty_takers(season_id)

        # 9. Recent opponent form (last 5 matches instead of full season)
        opponent_recent = await self.repo.get_opponent_recent_stats(season_id, n=5)

        # 10. Build predictions for players whose team has a fixture
        predictions: list[PlayerPrediction] = []
        for player_id, stats in player_stats.items():
            team_id = int(stats["team_id"])
            match_fix = team_fixture.get(team_id)
            if match_fix is None:
                continue

            is_home = int(match_fix["home_team_id"]) == team_id
            opponent_id = (
                int(match_fix["away_team_id"]) if is_home else int(match_fix["home_team_id"])
            )
            opponent_name = (
                str(match_fix["away_short"]) if is_home else str(match_fix["home_short"])
            )

            # Form (EWMA of last 5 matchdays; oldest → newest already ordered by repo)
            pts_list = recent_points.get(player_id, [])
            form_5: float | None = None
            if len(pts_list) >= 2:
                form_5 = round(_ewma(pts_list), 1)

            season_avg = stats["avg_pts"]
            form_val = form_5 if form_5 is not None else season_avg

            # Rival factor — use recent form (last 5 matches) if available
            opp_recent = opponent_recent.get(opponent_id, {})
            opp_season = opponent_stats.get(opponent_id, {})
            # Prefer recent form, fallback to season avg
            opp_goals_conceded = float(
                opp_recent.get(
                    "goals_conceded_avg", opp_season.get("goals_conceded_avg", league_avg_goals)
                )
            )
            position = stats["position"]
            if position in ("POR", "DEF"):
                rival_factor = league_avg_goals / max(opp_goals_conceded, 0.1)
            else:
                rival_factor = opp_goals_conceded / max(league_avg_goals, 0.1)
            # Clamp: a team that recently conceded ~0 would otherwise send the
            # raw ratio to ~10x and blow up the xPts. Keep it a modest nudge.
            rival_factor = max(_RIVAL_FACTOR_MIN, min(_RIVAL_FACTOR_MAX, rival_factor))

            # Location average
            loc = location_avgs.get(player_id, {})
            loc_key = "home_avg" if is_home else "away_avg"
            location_avg_raw: float | None = loc.get(loc_key)
            # Treat 0.0 as missing (player may not have played in that location yet)
            location_avg_used = location_avg_raw if location_avg_raw else season_avg
            location_avg_out: float | None = (
                round(location_avg_raw, 1) if location_avg_raw else None
            )

            # Starter probability discount
            starter_pct = starter_pcts.get(player_id, 1.0)
            is_penalty_taker = player_id in penalty_takers

            # xPts formula (weighted components * starter probability)
            raw_xpts = (
                (form_val * 0.40)
                + (season_avg * 0.20)
                + (season_avg * rival_factor * 0.25)
                + (location_avg_used * 0.15)
            )
            xpts = raw_xpts * starter_pct

            std_dev = stats["std_dev"]
            cv = std_dev / season_avg if season_avg > 0 else 1.0
            played = stats["matchdays_played"]
            # Confidence: low CV + enough games = alta, few games always caps at media
            if played < 5:
                confidence = "baja"
            elif played < 10 or cv >= 0.5:
                confidence = "media" if cv < 0.5 else "baja"
            else:
                confidence = "alta" if cv < 0.3 else "media"

            if form_5 is not None and season_avg > 0:
                if form_val > season_avg * 1.1:
                    trend = "rising"
                elif form_val < season_avg * 0.9:
                    trend = "falling"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            predictions.append(
                PlayerPrediction(
                    player_id=player_id,
                    player_name=stats["player_name"],
                    photo_path=stats["photo_path"],
                    position=position,
                    team_name=stats["team_name"],
                    opponent_name=opponent_name,
                    is_home=is_home,
                    season_avg=round(season_avg, 1),
                    form_5=form_5,
                    location_avg=location_avg_out,
                    rival_factor=round(rival_factor, 2),
                    xpts=round(xpts, 1),
                    xpts_floor=round(xpts - std_dev, 1),
                    xpts_ceiling=round(xpts + std_dev, 1),
                    confidence=confidence,
                    trend=trend,
                    matchdays_played=stats["matchdays_played"],
                    starter_pct=round(starter_pct * 100, 0),
                    is_penalty_taker=is_penalty_taker,
                )
            )

        # Sort by xpts descending for a useful default ordering
        predictions.sort(key=lambda p: p.xpts, reverse=True)

        # 8. Build opponent difficulty rankings
        all_gcas = [float(o["goals_conceded_avg"]) for o in opponent_stats.values()]
        if all_gcas:
            gca_sorted = sorted(all_gcas)
            n_teams = len(gca_sorted)
            # Thresholds: bottom third = easy (few goals conceded), top third = hard
            third = max(1, n_teams // 3)
            easy_threshold = gca_sorted[third - 1]
            hard_threshold = gca_sorted[n_teams - third]
        else:
            easy_threshold = hard_threshold = 0.0

        opponent_rankings: list[OpponentDifficulty] = []
        for opp_data in opponent_stats.values():
            gca = float(opp_data["goals_conceded_avg"])
            if gca <= easy_threshold:
                difficulty = "dificil"  # concedes few goals → hard to score against
            elif gca >= hard_threshold:
                difficulty = "facil"  # concedes many goals → easy to score against
            else:
                difficulty = "medio"
            opponent_rankings.append(
                OpponentDifficulty(
                    team_name=str(opp_data["team_name"]),
                    goals_conceded_avg=round(gca, 2),
                    clean_sheet_pct=round(float(opp_data["clean_sheet_pct"]) * 100, 1),
                    difficulty=difficulty,
                )
            )
        opponent_rankings.sort(key=lambda o: o.goals_conceded_avg)

        return PredictionsResponse(
            season_id=season_id,
            matchday_number=matchday_number,
            predictions=predictions,
            opponent_rankings=opponent_rankings,
        )
