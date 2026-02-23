from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MatchdaySummary(BaseModel):
    number: int
    status: str
    counts: bool
    stats_ok: bool
    first_match_at: datetime | None


class MatchdayListResponse(BaseModel):
    season_id: int
    matchdays: list[MatchdaySummary]


class MatchEntry(BaseModel):
    id: int
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    counts: bool
    played_at: datetime | None


class ParticipantScore(BaseModel):
    rank: int | None
    participant_id: int
    display_name: str
    total_points: int
    formation: str | None


class MatchdayDetailResponse(BaseModel):
    season_id: int
    number: int
    status: str
    counts: bool
    stats_ok: bool
    first_match_at: datetime | None
    matches: list[MatchEntry]
    scores: list[ParticipantScore]


class ScoreBreakdown(BaseModel):
    pts_play: int
    pts_starter: int
    pts_result: int
    pts_clean_sheet: int
    pts_goals: int
    pts_assists: int
    pts_yellow: int
    pts_red: int
    pts_marca: int
    pts_as: int
    pts_total: int


class LineupPlayerEntry(BaseModel):
    display_order: int
    position_slot: str
    player_id: int
    player_name: str
    team_name: str
    points: int
    score_breakdown: ScoreBreakdown | None


class LineupDetailResponse(BaseModel):
    participant_id: int
    display_name: str
    matchday_number: int
    formation: str
    total_points: int
    players: list[LineupPlayerEntry]
