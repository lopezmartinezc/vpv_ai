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
    display_name: str
    draft_order: int | None


class DraftPickEntry(BaseModel):
    pick_number: int
    round_number: int
    participant_id: int
    display_name: str
    draft_order: int | None
    player_name: str
    position: str
    team_name: str


class DraftDetailResponse(BaseModel):
    season_id: int
    phase: str
    draft_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    participants: list[DraftParticipant]
    picks: list[DraftPickEntry]


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
    participant_id: int
    player_id: int


class AddPickResponse(BaseModel):
    pick_number: int
    round_number: int
    participant_id: int
    display_name: str
    player_name: str
    position: str
    team_name: str


class DeletePickResponse(BaseModel):
    deleted_pick_number: int


class PlayerSearchItem(BaseModel):
    id: int
    display_name: str
    position: str
    team_name: str
    photo_path: str | None
    is_already_picked: bool


class PlayerSearchResponse(BaseModel):
    players: list[PlayerSearchItem]
