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


class SquadPlayerForLineup(BaseModel):
    """Player entry from the user's squad, for lineup selection."""

    player_id: int
    display_name: str
    photo_path: str | None = None
    position: str
    team_name: str
    season_points: int


class MyLineupResponse(BaseModel):
    participant_id: int
    display_name: str
    lineup_deadline_min: int
    current_lineup: LineupSubmitResponse | None = None
    squad: list[SquadPlayerForLineup]
