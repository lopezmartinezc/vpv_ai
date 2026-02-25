from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SeasonSummary(BaseModel):
    id: int
    name: str
    status: str
    matchday_current: int
    total_participants: int

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
    created_at: datetime

    model_config = {"from_attributes": True}


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
