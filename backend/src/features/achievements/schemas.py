from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AchievementDefinitionResponse(BaseModel):
    id: int
    achievement_key: str
    name: str
    description: str
    category: str
    icon: str
    max_tier: int
    repeatable: bool


class AchievementEntry(BaseModel):
    id: int
    achievement_key: str
    name: str
    description: str
    icon: str
    category: str
    tier: int
    participant_id: int
    display_name: str
    matchday_number: int | None
    metadata: dict | None
    created_at: datetime


class SeasonAchievementsResponse(BaseModel):
    season_id: int
    achievements: list[AchievementEntry]


class EvaluationResult(BaseModel):
    matchday_number: int
    evaluated: int
    granted: int
