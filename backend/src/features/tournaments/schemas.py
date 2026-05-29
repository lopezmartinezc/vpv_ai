from __future__ import annotations

from typing import Any

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
    # Pairing placeholders (from tournament_config) when team not yet known
    match_code: str | None = None
    home_placeholder: str | None = None
    away_placeholder: str | None = None
    label: str | None = None


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
    bracket_predictions: dict[str, Any] | None = None


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
    bracket_predictions: dict[str, Any] | None = None


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
    position: str | None = None
    photo_path: str | None = None


class TeamGroupAssignment(BaseModel):
    team_id: int
    group_name: str | None  # 'A', 'B', ..., or null to unassign


class TeamGroupBatchUpdate(BaseModel):
    assignments: list[TeamGroupAssignment]


# --- Auto-scoring ---


class PredictionScoreBreakdown(BaseModel):
    user_id: int
    display_name: str | None
    total: int
    detail: dict[str, int]


class RecalculateResponse(BaseModel):
    season_id: int
    scoring_rules: dict[str, int]
    actuals: dict[str, Any]
    results: list[PredictionScoreBreakdown]


# --- Predictions status ---


class PredictionsStatusResponse(BaseModel):
    season_id: int
    locked: bool
    deadline_at: str | None  # ISO datetime, or null if no first match scheduled
    first_match_at: str | None


# --- Third-place assignments (FIFA WC 2026 Annex C) ---


class ThirdPlaceAssignmentsRequest(BaseModel):
    """The 8 group letters whose 3rd-placed team qualifies to the R32."""

    groups: list[str]


class ThirdPlaceAssignmentsResponse(BaseModel):
    """Deterministic mapping from R32 match_code to the 3-of-group placeholder.

    Example: ``{"M74": "3A", "M75": "3D", ...}``. When the input groups don't
    form a valid Annex C row (i.e. not exactly 8 different letters from A..L),
    ``assignments`` is ``None``.
    """

    groups: list[str]
    assignments: dict[str, str] | None
