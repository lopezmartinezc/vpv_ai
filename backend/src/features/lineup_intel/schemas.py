from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SourceReading(BaseModel):
    source: str
    probability: int | None
    previous_probability: int | None
    starter: bool
    status: str | None
    note: str | None
    fetched_at: datetime


class PlayerReadings(BaseModel):
    player_id: int
    readings: list[SourceReading]


class UnmatchedReading(BaseModel):
    """A name a source lists that could not be matched to one of ours."""

    team_id: int
    raw_name: str
    reading: SourceReading


class NewsItem(BaseModel):
    team_id: int
    source: str
    title: str
    url: str
    published_at: datetime | None


class LineupIntelResponse(BaseModel):
    season_id: int
    matchday_number: int
    updated_at: datetime | None
    players: list[PlayerReadings]
    unmatched: list[UnmatchedReading]
    news: list[NewsItem]


class SourceSummary(BaseModel):
    rows: int
    matched: int
    news: int
    errors: list[str]


class RefreshResponse(BaseModel):
    sources: dict[str, SourceSummary]
