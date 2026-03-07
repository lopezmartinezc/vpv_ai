from __future__ import annotations

from pydantic import BaseModel


class PlayerListItem(BaseModel):
    id: int
    display_name: str
    slug: str
    position: str
    team_id: int
    team_name: str
    owner_name: str | None
    is_available: bool


class PlayerListResponse(BaseModel):
    season_id: int
    players: list[PlayerListItem]
    total: int


class TeamOption(BaseModel):
    id: int
    name: str


class PlayerUpdateRequest(BaseModel):
    team_id: int | None = None
    position: str | None = None


class PlayerUpdateResponse(BaseModel):
    id: int
    display_name: str
    team_id: int
    team_name: str
    position: str
