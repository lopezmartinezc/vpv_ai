from __future__ import annotations

from pydantic import BaseModel


class StandingEntry(BaseModel):
    rank: int
    participant_id: int
    display_name: str
    total_points: int
    matchdays_played: int
    avg_points: float


class StandingsResponse(BaseModel):
    season_id: int
    season_name: str
    entries: list[StandingEntry]
