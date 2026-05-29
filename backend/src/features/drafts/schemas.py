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
    player_id: int
    avg_pts: float
    std_dev: float
    form_5: float | None
    trend: str  # "rising" | "stable" | "falling"
    matchdays_played: int
    starter_pct: float


class DraftPlayerStatsResponse(BaseModel):
    players: dict[str, PlayerDraftStats]  # keyed by player_id as string
    suggestions: dict[str, list[int]]  # position -> [top 5 player_ids]
