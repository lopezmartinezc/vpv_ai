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
