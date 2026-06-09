"""Schemas for retrospective draft analytics.

Endpoints:
- /stats/admin/drafts/{draft_id}/retrospective — per-pick post-mortem
- /stats/admin/drafts/scatter — every pick across seasons, for charting
- /stats/admin/drafts/backtest — did the scorecard hold up?
- /stats/admin/drafts/participant-iq — who picks well across seasons
"""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Endpoint 1: retrospective of a single draft
# ---------------------------------------------------------------------------


class RetroPick(BaseModel):
    pick_number: int
    round_number: int
    participant_id: int
    participant_display_name: str

    player_id: int
    player_name: str
    position: str
    team_name: str
    photo_path: str | None

    # How the player actually performed in the season this draft belongs to.
    season_total_points: float
    season_avg_pts: float
    matchdays_played: int

    # Baseline: median total_points of all picks taken at this same pick_number
    # across the historical seasons (5,6,7,8). NULL if no comparable data.
    slot_median_total_points: float | None

    # delta = season_total_points - slot_median_total_points
    # (positive = better than the slot baseline = steal; negative = bust).
    delta_vs_slot: float | None

    # Tag derived from `delta_vs_slot` relative to other picks in the same draft.
    # Top quartile = "steal", bottom quartile = "bust", middle = "normal".
    tag: str  # "steal" | "bust" | "normal"


class DraftRetrospectiveResponse(BaseModel):
    draft_id: int
    season_id: int
    season_name: str
    phase: str
    n_picks: int
    picks: list[RetroPick]


# ---------------------------------------------------------------------------
# Endpoint 2: scatter of all historical picks
# ---------------------------------------------------------------------------


class PickPoint(BaseModel):
    pick_number: int
    round_number: int
    total_points: float
    avg_points: float
    matchdays_played: int
    position: str
    player_id: int
    player_name: str
    team_name: str
    season_id: int
    season_name: str
    phase: str
    participant_display_name: str


class DraftScatterResponse(BaseModel):
    season_ids: list[int]
    phases: list[str]
    n_points: int
    points: list[PickPoint]
    # Aggregated curve: pick_number -> median(total_points) across all picks.
    # Useful to draw a trendline on top of the scatter.
    slot_curve: dict[int, float]


# ---------------------------------------------------------------------------
# Endpoint 3: backtest of the scorecard
# ---------------------------------------------------------------------------


class BacktestPoint(BaseModel):
    player_id: int
    player_name: str
    position: str
    seasons_history: int  # how many past seasons we had to train on

    predicted_effective_score: float
    predicted_signal: str  # strong_buy | buy | hold | avoid
    predicted_tier: str  # elite | solid | normal | weak

    actual_total_points: float
    actual_avg_points: float
    actual_matchdays_played: int


class SignalBucket(BaseModel):
    n: int
    mean_actual: float
    median_actual: float


class BacktestResponse(BaseModel):
    season_id: int
    season_name: str
    n_players: int

    # Spearman rank correlation between predicted_effective_score and
    # actual_total_points. Sanity check: should be ≥ 0.5 for the model
    # to be worth showing.
    spearman_rank_correlation: float

    by_signal: dict[str, SignalBucket]  # {"strong_buy": {...}, ...}
    by_tier: dict[str, SignalBucket]  # {"elite": {...}, ...}

    points: list[BacktestPoint]


# ---------------------------------------------------------------------------
# Endpoint 4: draft IQ per participant
# ---------------------------------------------------------------------------


class BestPickHighlight(BaseModel):
    player_name: str
    season_name: str
    pick_number: int
    round_number: int
    delta_vs_slot: float


class ParticipantIQ(BaseModel):
    participant_id: int
    display_name: str
    n_drafts: int
    total_picks: int
    sum_delta_vs_slot: float
    mean_delta_per_pick: float
    best_pick: BestPickHighlight | None
    worst_pick: BestPickHighlight | None
    # round_number -> mean_delta_for_that_round. Reveals whether a
    # participant is good at R1 vs late-round picks.
    by_round: dict[int, float]


class ParticipantIQResponse(BaseModel):
    phase: str
    min_seasons: int
    participants: list[ParticipantIQ]
