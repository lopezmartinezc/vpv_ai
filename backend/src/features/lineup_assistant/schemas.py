from __future__ import annotations

from pydantic import BaseModel, Field


class LineupChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class LineupAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[LineupChatMessage] = Field(default_factory=list, max_length=40)
    # Null uses ASSISTANT_PROVIDER / the provider's default model.
    provider: str | None = Field(default=None, pattern="^(anthropic|openai)$")
    model: str | None = Field(default=None, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")


class LineupToolCall(BaseModel):
    name: str
    arguments: dict[str, object]


class LineupAskResponse(BaseModel):
    reply: str
    provider: str
    model: str
    tool_calls: list[LineupToolCall]
    truncated: bool


class SuggestedPlayer(BaseModel):
    player_id: int
    name: str
    position: str
    team_name: str
    # Expected points of the choice: xpts_if_plays x play_prob.
    value: float
    xpts_if_plays: float | None
    play_prob: float
    # Where the chance comes from, in words.
    basis: str


class SuggestionResponse(BaseModel):
    season_id: int
    matchday_number: int
    formation: str
    total: float
    eleven: list[SuggestedPlayer]
    bench: list[SuggestedPlayer]
