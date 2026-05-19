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
