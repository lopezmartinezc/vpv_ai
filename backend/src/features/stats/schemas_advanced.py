"""Pydantic schemas for the advanced statistics feature.

Phase 1: Advanced player metrics (percentiles, CI, trend, pp90).
"""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Phase 1 — Advanced player metrics
# ---------------------------------------------------------------------------


class AdvancedPlayerStat(BaseModel):
    """Per-player advanced statistical metrics for a season."""

    player_id: int
    display_name: str
    photo_path: str | None
    position: str
    team_name: str
    # Participation
    matchdays_played: int
    minutes_played: int
    # Points
    total_points: int
    avg_points: float
    # Dispersion
    std_dev: float  # Sample standard deviation of pts_total
    cv: float  # Coefficient of variation (std_dev / avg_points)
    # Percentiles (of pts_total distribution)
    p10: float  # 10th percentile — floor
    p50: float  # 50th percentile — median
    p90: float  # 90th percentile — ceiling
    # Minutes-adjusted
    pp90: float  # Points per 90 minutes
    # Confidence interval (95%)
    ci_lower: float
    ci_upper: float
    # Form / trend
    form_5: float | None  # EWMA of last 5 matchdays (None if < 5 played)
    trend: str  # "rising" | "stable" | "falling"


class AdvancedPlayersResponse(BaseModel):
    season_id: int
    players: list[AdvancedPlayerStat]


# ---------------------------------------------------------------------------
# Phase 2 — Position value analysis
# ---------------------------------------------------------------------------


class PositionTierPlayer(BaseModel):
    player_id: int
    display_name: str
    team_name: str
    total_points: int
    par: float  # Points Above Replacement


class PositionTier(BaseModel):
    tier: int  # 1=Elite, 2=Solid, 3=Average, 4=Replaceable
    label: str
    min_points: float
    max_points: float
    players: list[PositionTierPlayer]


class PositionAnalysis(BaseModel):
    position: str
    player_count: int
    replacement_level: float
    avg_points: float
    median_points: float
    scarcity_index: float  # Ratio of elite players to total
    tiers: list[PositionTier]


class PositionValueResponse(BaseModel):
    season_id: int
    positions: list[PositionAnalysis]


# ---------------------------------------------------------------------------
# Phase 3 — Draft history
# ---------------------------------------------------------------------------


class PickValuePoint(BaseModel):
    pick_number: int
    avg_total_points: float
    sample_count: int


class PositionRoundValue(BaseModel):
    round_number: int
    position: str
    avg_total_points: float
    pick_count: int


class RateEntry(BaseModel):
    round_range: str
    rate_pct: float
    total_picks: int


class DraftHistoryResponse(BaseModel):
    pick_value_curve: list[PickValuePoint]
    position_by_round: list[PositionRoundValue]
    bust_rate: list[RateEntry]
    steal_rate: list[RateEntry]


# ---------------------------------------------------------------------------
# Phase 4 — Context analysis
# ---------------------------------------------------------------------------


class PlayerSplit(BaseModel):
    location: str  # "home" | "away"
    matches: int
    avg_points: float
    total_points: int
    goals: int
    assists: int


class PlayerSplitsResponse(BaseModel):
    player_id: int
    display_name: str
    season_id: int
    splits: list[PlayerSplit]


class TeamDependencyEntry(BaseModel):
    team_name: str
    top_player_name: str
    top_player_id: int
    top_player_points: int
    team_total_points: int
    dependency_pct: float


class TeamDependencyResponse(BaseModel):
    season_id: int
    entries: list[TeamDependencyEntry]


class ComparePlayerAxis(BaseModel):
    player_id: int
    display_name: str
    photo_path: str | None
    position: str
    team_name: str
    goals_rate: float  # goals per match, normalized 0-100
    assists_rate: float  # assists per match, normalized 0-100
    avg_points: float  # normalized 0-100
    consistency: float  # 1 - CV, normalized 0-100
    pp90: float  # normalized 0-100
    form: float  # form_5 or avg, normalized 0-100


class ComparePlayersResponse(BaseModel):
    season_id: int
    players: list[ComparePlayerAxis]
