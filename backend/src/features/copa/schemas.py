from __future__ import annotations

from pydantic import BaseModel


class CopaMatchdayResult(BaseModel):
    participant_id: int
    display_name: str
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int  # 3=win, 1=draw, 0=loss


class CopaMatchdayDetail(BaseModel):
    matchday_number: int
    results: list[CopaMatchdayResult]


class CopaStandingEntry(BaseModel):
    rank: int
    participant_id: int
    display_name: str
    total_points: int
    matches_played: int
    wins: int
    draws: int
    losses: int
    total_goals_for: int
    total_goals_against: int
    goal_difference: int


class CopaFullResponse(BaseModel):
    season_id: int
    season_name: str
    standings: list[CopaStandingEntry]
    matchdays: list[CopaMatchdayDetail]
