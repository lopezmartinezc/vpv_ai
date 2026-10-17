from __future__ import annotations

from pydantic import BaseModel, Field


class LineupChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class LineupDraftSlot(BaseModel):
    player_id: int
    position_slot: str = Field(pattern="^(POR|DEF|MED|DEL)$")


class LineupDraft(BaseModel):
    """The eleven being edited on the screen, not yet sent. Partial while the
    user is still picking; the formation only once eleven are in."""

    formation: str | None = Field(default=None, pattern=r"^1-\d-\d-\d$")
    players: list[LineupDraftSlot] = Field(default_factory=list, max_length=11)


class LineupAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[LineupChatMessage] = Field(default_factory=list, max_length=40)
    # What the screen shows right now; null when asked from elsewhere.
    draft: LineupDraft | None = None
    # Null uses ASSISTANT_PROVIDER / the provider's default model.
    provider: str | None = Field(default=None, pattern="^(anthropic|openai)$")
    model: str | None = Field(default=None, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")


class LineupToolCall(BaseModel):
    name: str
    arguments: dict[str, object]


class ProposedPlayerOut(BaseModel):
    player_id: int
    name: str
    position: str


class LineupProposal(BaseModel):
    """An eleven the chat proposes, checked by the server, for the screen to
    apply in one click. Entering/leaving are against the draft it was asked
    about (or the saved eleven when there was no draft)."""

    formation: str
    players: list[ProposedPlayerOut]
    entering: list[str]
    leaving: list[str]
    basis: str


class LineupAskResponse(BaseModel):
    reply: str
    provider: str
    model: str
    tool_calls: list[LineupToolCall]
    truncated: bool
    proposal: LineupProposal | None = None


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
