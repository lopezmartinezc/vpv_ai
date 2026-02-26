from __future__ import annotations

from pydantic import BaseModel


class PositionCounts(BaseModel):
    POR: int = 0
    DEF: int = 0
    MED: int = 0
    DEL: int = 0


class SquadSummary(BaseModel):
    participant_id: int
    display_name: str
    total_players: int
    season_points: int
    positions: PositionCounts


class SquadListResponse(BaseModel):
    season_id: int
    squads: list[SquadSummary]


class SquadPlayerEntry(BaseModel):
    player_id: int
    display_name: str
    photo_path: str | None
    position: str
    team_name: str
    season_points: int


class SquadDetailResponse(BaseModel):
    participant_id: int
    display_name: str
    season_points: int
    players: list[SquadPlayerEntry]
