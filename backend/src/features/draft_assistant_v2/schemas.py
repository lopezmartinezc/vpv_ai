from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Position = Literal["POR", "DEF", "MED", "DEL"]
ProviderName = Literal["openai", "anthropic"]
PositiveId = Annotated[int, Field(gt=0, strict=True)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ViewContext(StrictModel):
    selected_player_ids: list[PositiveId] = Field(default_factory=list, max_length=3)
    participant_id: PositiveId | None = None
    position: Position | None = None
    team: str = Field(default="", max_length=100)
    search: str = Field(default="", max_length=100)
    order: Literal["priority", "vorp", "gain"] = "priority"


class AskRequest(StrictModel):
    question: str = Field(min_length=1, max_length=4000)
    provider: ProviderName
    model: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")
    participation: Literal["mixto", "historico"] = "mixto"
    mode: Literal["quick", "detailed"] = "quick"
    context: ViewContext = Field(default_factory=ViewContext)


class Revision(StrictModel):
    draft: str
    board: str
    at: str
    pick_count: int


class Card(StrictModel):
    player_id: int
    name: str
    position: str
    team: str
    available: bool
    priority: float | None
    priority_base: float | None
    vorp: float | None
    participation: float | None
    available_gap: float | None = None
    marginal_gain: float | None = None
    # What a side-by-side needs beyond the ranking: how much he scores when
    # he plays, how much he plays, and how much evidence sits behind it.
    avg_points: float | None = None
    games_played: int = 0
    seasons_played: int = 0
    availability: float | None = None
    exp_games_remaining: float | None = None
    is_new: bool = False
    team_changed: bool = False
    position_changed: bool = False
    tags: list[str] = Field(default_factory=list)
    evidence_id: str


class Usage(StrictModel):
    input_tokens: int = 0
    # Of the input, how much the provider served from its prefix cache. The
    # total is not the bill; this is what makes the bill legible.
    cached_tokens: int = 0
    output_tokens: int = 0
    rounds: int = 0
    tool_calls: int = 0
    latency_ms: int = 0
    # Why the engine stopped without an answer. None when it finished normally.
    # Three different walls with three different fixes, and the person who can
    # act on it is the one looking at the screen.
    stop_reason: str | None = None


class Answer(StrictModel):
    text: str
    cards: list[Card] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["current", "stale", "incomplete"] = "current"
    warnings: list[str] = Field(default_factory=list)
    revision: Revision
    provider: str
    model: str
    usage: Usage = Field(default_factory=Usage)


class Exchange(StrictModel):
    question: str
    answer: Answer


class History(StrictModel):
    exchanges: list[Exchange] = Field(default_factory=list)


class ProviderOption(StrictModel):
    name: ProviderName
    models: list[str]
    default_model: str


class Capabilities(StrictModel):
    enabled: bool
    providers: list[ProviderOption]
    default: str
