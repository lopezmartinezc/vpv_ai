from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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


class SourceCoverage(BaseModel):
    """A predicted11 predictor has an eleven for this team: the players in it
    count 100 for that predictor, and the rest of the team 0."""

    source: str  # predicted11_1 | predicted11_2 | predicted11_3
    team_id: int
    team_name: str
    # Who the predictor is: "watusi74, 1.º del destacado del Rayo (81,8 % de acierto)".
    note: str | None


class LineupIntelResponse(BaseModel):
    season_id: int
    matchday_number: int
    updated_at: datetime | None
    players: list[PlayerReadings]
    unmatched: list[UnmatchedReading]
    news: list[NewsItem]
    coverage: list[SourceCoverage] = Field(default_factory=list)


class RefreshStarted(BaseModel):
    """A refresh runs in the background: with predicted11 it takes minutes,
    longer than a request may wait behind the proxy."""

    started: bool = True
    message: str = "Actualizando las alineaciones probables en segundo plano: tarda unos minutos."
