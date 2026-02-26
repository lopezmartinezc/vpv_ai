from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ParticipantBalance(BaseModel):
    participant_id: int
    display_name: str
    initial_fee: float
    weekly_total: float
    draft_fees: float
    net_balance: float


class EconomyResponse(BaseModel):
    season_id: int
    balances: list[ParticipantBalance]


class TransactionEntry(BaseModel):
    id: int
    type: str
    amount: float
    description: str | None
    matchday_number: int | None
    created_at: datetime


class ParticipantEconomyResponse(BaseModel):
    participant_id: int
    display_name: str
    net_balance: float
    transactions: list[TransactionEntry]


# --- Admin schemas ---


class TransactionCreateRequest(BaseModel):
    participant_id: int
    type: str
    amount: float
    description: str | None = None
    matchday_id: int | None = None
