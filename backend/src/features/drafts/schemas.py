from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DraftSummary(BaseModel):
    id: int
    phase: str
    draft_type: str
    status: str
    total_picks: int
    started_at: datetime | None
    completed_at: datetime | None


class DraftListResponse(BaseModel):
    season_id: int
    drafts: list[DraftSummary]


class DraftParticipant(BaseModel):
    participant_id: int
    user_id: int
    display_name: str
    draft_order: int | None


class DraftPickEntry(BaseModel):
    id: int
    pick_number: int
    round_number: int
    participant_id: int
    display_name: str
    draft_order: int | None
    player_id: int
    player_name: str
    position: str
    team_name: str
    photo_path: str | None = None
    dropped_player_name: str | None = None


class DraftDetailResponse(BaseModel):
    id: int
    season_id: int
    phase: str
    draft_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    participants: list[DraftParticipant]
    picks: list[DraftPickEntry]
    next_participant_id: int | None = None


# ---------------------------------------------------------------------------
# Draft management (write operations)
# ---------------------------------------------------------------------------


class ParticipantOrderItem(BaseModel):
    participant_id: int
    draft_order: int


class UpdateDraftOrderRequest(BaseModel):
    orders: list[ParticipantOrderItem]


class CreateDraftRequest(BaseModel):
    phase: str  # "preseason" | "winter"
    draft_type: str  # "snake" | "linear"


class CreateDraftResponse(BaseModel):
    id: int
    season_id: int
    phase: str
    draft_type: str
    status: str


class AddPickRequest(BaseModel):
    player_id: int
    participant_id: int | None = None  # Auto-determined by draft order if omitted


class AddPickResponse(BaseModel):
    pick_number: int
    round_number: int
    participant_id: int
    display_name: str
    player_id: int
    player_name: str
    position: str
    team_name: str
    photo_path: str | None = None
    origin: str = "manual"


class DeletePickResponse(BaseModel):
    deleted_pick_number: int


class ReorderPicksRequest(BaseModel):
    pick_ids: list[int]  # DraftPick IDs in desired order


class ReorderPicksResponse(BaseModel):
    reordered: int


class PlayerSearchItem(BaseModel):
    id: int
    display_name: str
    position: str
    team_name: str
    photo_path: str | None
    is_already_picked: bool


class PlayerSearchResponse(BaseModel):
    players: list[PlayerSearchItem]


class DraftTeamOption(BaseModel):
    """A team in the draft's season, used by the player-search filter."""

    id: int
    name: str


# ---------------------------------------------------------------------------
# Admin — live draft player stats
# ---------------------------------------------------------------------------


class PlayerDraftStats(BaseModel):
    """Snapshot served to the live-draft admin UI.

    Combines the Ensemble model output (ensemble_score, signal,
    reasons) with the heuristic overrides documented in
    docs/DRAFT_SCORECARD.md: per-position tiers, survival haircut,
    and warning flags for movers, year-peakers, and likely
    penalty-takers (DEL).
    """

    player_id: int

    # Raw model output
    ensemble_score: float
    signal: str  # "strong_buy" | "buy" | "hold" | "avoid"
    signal_reasons: list[str]

    # Scorecard-derived
    position_tier: str  # "elite" | "solid" | "normal" | "weak" | "team_dependent" (POR)
    survival_haircut_pct: float  # 0..1 (0.22 = 22% trim)
    effective_score: float  # ensemble_score * (1 - haircut)
    is_mover: bool  # changed team since the previous season
    is_peak_year: bool  # last season was their best (regression risk)
    is_likely_penalty_taker: bool  # DEL only; ≥2 pen attempts last season
    is_bench_risk: bool  # starter_pct < 0.79 OR games_played < 22 (p50)
    # If is_mover: how many pts to mentally subtract when the team-quality
    # jump is large (POR 2.0, others 1.0). UI shows it as a hint; the
    # effective_score does NOT apply it automatically.
    mover_penalty_hint: float | None

    # Useful supporting numbers shown in the card
    avg_pts: float
    matchdays_played: int
    starter_pct: float


class DraftPlayerStatsResponse(BaseModel):
    players: dict[str, PlayerDraftStats]  # keyed by player_id as string
    suggestions: dict[str, list[int]]  # position -> [top 5 player_ids]
