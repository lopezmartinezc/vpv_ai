from __future__ import annotations

from pydantic import BaseModel


class PodiumEntry(BaseModel):
    rank: int
    user_id: int
    display_name: str
    total_points: int
    matchdays_played: int


class SeasonChampion(BaseModel):
    season_id: int
    season_name: str
    entries: list[PodiumEntry]


class CareerEntry(BaseModel):
    user_id: int
    display_name: str
    seasons_played: int
    championships: int
    podiums: int
    total_points: int
    total_matchdays: int
    avg_points: float
    best_finish: int
    best_season_name: str


class AllTimeRecord(BaseModel):
    label: str
    value: str
    detail: str


class PalmaresResponse(BaseModel):
    champions: list[SeasonChampion]
    career: list[CareerEntry]
    records: list[AllTimeRecord]
