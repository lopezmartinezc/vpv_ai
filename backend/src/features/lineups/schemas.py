from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class LineupPlayerSlot(BaseModel):
    player_id: int
    position_slot: str  # "POR", "DEF", "MED", "DEL"

    @field_validator("position_slot")
    @classmethod
    def validate_position(cls, v: str) -> str:
        v = v.upper()
        if v not in ("POR", "DEF", "MED", "DEL"):
            raise ValueError(f"Posicion invalida: {v}")
        return v


class LineupSubmitRequest(BaseModel):
    formation: str  # e.g. "1-4-3-3"
    players: list[LineupPlayerSlot]

    @field_validator("players")
    @classmethod
    def validate_player_count(cls, v: list[LineupPlayerSlot]) -> list[LineupPlayerSlot]:
        if len(v) != 11:
            raise ValueError("La alineacion debe tener exactamente 11 jugadores")
        return v


class LineupPlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    player_name: str
    position_slot: str
    display_order: int
    photo_path: str | None = None


class LineupSubmitResponse(BaseModel):
    lineup_id: int
    formation: str
    confirmed: bool
    confirmed_at: datetime | None = None
    telegram_sent: bool
    players: list[LineupPlayerResponse]


class FormMatch(BaseModel):
    played: bool
    result: int  # 0=L, 1=D, 2=W (only meaningful when played=True)
    is_home: bool
    points: int


class PlayerRecentForm(BaseModel):
    matches: list[FormMatch]  # last 5, oldest→newest
    clean_sheets: int
    goals: int
    assists: int
    penalty_goals: int
    yellow_cards: int


class SquadPlayerForLineup(BaseModel):
    """Player entry from the user's squad, for lineup selection."""

    player_id: int
    display_name: str
    photo_path: str | None = None
    position: str
    team_name: str
    season_points: int
    recent_form: PlayerRecentForm | None = None


class MyLineupResponse(BaseModel):
    participant_id: int
    display_name: str
    lineup_deadline_min: int
    current_lineup: LineupSubmitResponse | None = None
    squad: list[SquadPlayerForLineup]


class DeadlineStatusResponse(BaseModel):
    has_lineup: bool
    deadline_at: datetime | None = None
    minutes_remaining: int | None = None
    matchday_number: int


class LineupHistoryPlayerEntry(BaseModel):
    player_id: int
    player_name: str
    position_slot: str
    display_order: int
    photo_path: str | None = None
    points: int


class LineupHistoryEntry(BaseModel):
    matchday_number: int
    formation: str
    total_points: int
    confirmed_at: datetime | None = None
    players: list[LineupHistoryPlayerEntry]


class LineupHistoryResponse(BaseModel):
    participant_id: int
    display_name: str
    season_name: str
    lineups: list[LineupHistoryEntry]


class MissedCall(BaseModel):
    position: str
    benched_name: str
    benched_points: int
    lined_up_name: str
    lined_up_points: int


class MatchdayAccuracy(BaseModel):
    matchday_number: int
    actual_points: int
    optimal_points: int
    accuracy_pct: float
    formation_used: str
    optimal_formation: str
    missed_calls: list[MissedCall]


class AccuracyResponse(BaseModel):
    participant_id: int
    display_name: str
    season_name: str
    avg_accuracy: float
    perfect_weeks: int
    total_missed_points: int
    matchdays: list[MatchdayAccuracy]
