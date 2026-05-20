from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class SeasonSummary(BaseModel):
    id: int
    name: str
    status: str
    matchday_current: int
    total_participants: int
    lineup_deadline_min: int
    kind: str = "league"
    tournament_type: str | None = None

    model_config = {"from_attributes": True}


class SeasonDetail(BaseModel):
    id: int
    name: str
    status: str
    matchday_start: int
    matchday_end: int | None
    matchday_current: int
    matchday_winter: int | None
    matchday_scanned: int
    draft_pool_size: int
    lineup_deadline_min: int
    total_participants: int
    scraping_slug: str | None = None
    edit_unlocked: bool = False
    kind: str = "league"
    tournament_type: str | None = None
    tournament_config: dict[str, Any] | None = None
    telegram_chat_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EditUnlockRequest(BaseModel):
    unlocked: bool


class ScoringRuleResponse(BaseModel):
    id: int
    rule_key: str
    position: str | None
    value: Decimal
    description: str | None

    model_config = {"from_attributes": True}


class SeasonPaymentResponse(BaseModel):
    id: int
    payment_type: str
    position_rank: int | None
    amount: Decimal
    description: str | None

    model_config = {"from_attributes": True}


class ValidFormationResponse(BaseModel):
    id: int
    formation: str
    defenders: int
    midfielders: int
    forwards: int

    model_config = {"from_attributes": True}


# --- Admin schemas ---


class SeasonUpdateRequest(BaseModel):
    status: str | None = None
    name: str | None = None
    matchday_start: int | None = None
    matchday_current: int | None = None
    matchday_end: int | None = None
    matchday_winter: int | None = None
    lineup_deadline_min: int | None = None
    draft_pool_size: int | None = None
    scraping_slug: str | None = None
    tournament_config: dict[str, Any] | None = None
    telegram_chat_id: str | None = None


class ScoringRuleUpdateRequest(BaseModel):
    id: int
    value: Decimal


class ScoringRulesBatchUpdate(BaseModel):
    rules: list[ScoringRuleUpdateRequest]


class PaymentUpdateRequest(BaseModel):
    id: int
    amount: Decimal


class PaymentsBatchUpdate(BaseModel):
    payments: list[PaymentUpdateRequest]


class PaymentUpsertRequest(BaseModel):
    payment_type: str
    position_rank: int | None = None
    amount: Decimal
    description: str | None = None


class SeasonParticipantResponse(BaseModel):
    id: int
    user_id: int
    display_name: str
    draft_order: int | None
    is_active: bool
    group_name: str | None = None

    model_config = {"from_attributes": True}


class GroupAssignRequest(BaseModel):
    group_name: str | None = None


class AddParticipantRequest(BaseModel):
    user_id: int


# --- Season lifecycle schemas ---


class SeasonInitializeRequest(BaseModel):
    name: str
    scraping_slug: str
    matchday_start: int = 1
    matchday_end: int = 38
    draft_pool_size: int = 26
    lineup_deadline_min: int = 30
    copy_from_season_id: int | None = None
    participant_user_ids: list[int] | None = None
    kind: str = "league"
    tournament_type: str | None = None
    tournament_config: dict[str, Any] | None = None
    telegram_chat_id: str | None = None


class SeasonInitializeResponse(BaseModel):
    season: SeasonDetail
    participants_created: int
    scoring_rules_copied: int
    payments_copied: int
    matchdays_created: int
    scraping_started: bool


class PhotoDownloadResponse(BaseModel):
    downloaded: int
    skipped: int
    errors: int
    restored: int


class SeasonFinalizeResponse(BaseModel):
    season: SeasonDetail
