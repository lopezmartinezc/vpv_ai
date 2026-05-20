from __future__ import annotations

from pydantic import BaseModel


class TeamGroupStanding(BaseModel):
    """Stats of a team in its group."""

    team_id: int
    team_name: str
    short_name: str | None
    logo_path: str | None
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_diff: int
    points: int


class GroupResponse(BaseModel):
    name: str
    teams: list[TeamGroupStanding]


class GroupsResponse(BaseModel):
    season_id: int
    season_name: str
    tournament_type: str | None
    groups: list[GroupResponse]


class BracketMatch(BaseModel):
    match_id: int | None
    home_team_id: int | None
    home_team_name: str | None
    home_logo: str | None
    home_score: int | None
    away_team_id: int | None
    away_team_name: str | None
    away_logo: str | None
    away_score: int | None
    played: bool


class BracketRound(BaseModel):
    name: str
    matchday: int
    matches: list[BracketMatch]


class BracketResponse(BaseModel):
    season_id: int
    season_name: str
    rounds: list[BracketRound]


# --- Predictions ---


class PredictionRequest(BaseModel):
    winner_team_id: int | None = None
    top_scorer_player_id: int | None = None
    best_player_id: int | None = None
    dark_horse_team_id: int | None = None
    notes: str | None = None


class PredictionResponse(BaseModel):
    id: int
    season_id: int
    user_id: int
    display_name: str | None = None
    winner_team_id: int | None
    winner_team_name: str | None = None
    top_scorer_player_id: int | None
    top_scorer_player_name: str | None = None
    best_player_id: int | None
    best_player_name: str | None = None
    dark_horse_team_id: int | None
    dark_horse_team_name: str | None = None
    notes: str | None
    bonus_points: int


class PredictionsListResponse(BaseModel):
    season_id: int
    season_name: str
    predictions: list[PredictionResponse]


class TeamOption(BaseModel):
    id: int
    name: str
    short_name: str | None
    logo_path: str | None
    tournament_group: str | None


class PlayerOption(BaseModel):
    id: int
    name: str
    team_name: str
    team_id: int


class TeamGroupAssignment(BaseModel):
    team_id: int
    group_name: str | None  # 'A', 'B', ..., or null to unassign


class TeamGroupBatchUpdate(BaseModel):
    assignments: list[TeamGroupAssignment]
