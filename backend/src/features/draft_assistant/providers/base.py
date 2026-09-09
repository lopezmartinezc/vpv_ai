"""The provider contract the draft assistant talks to.

Conversation history is kept as plain user/assistant text. Tool calls live and
die inside a single ``run()``: the model sees its own tool results within the
turn, but earlier turns are replayed as its prose summary rather than as raw
tool blocks. That is what keeps the history portable between providers — the
two wire formats for tool traffic have nothing in common — at the cost of the
model not being able to re-read a previous turn's raw rows. For a draft chat,
where questions are largely self-contained and the data is one tool call away,
that is a good trade.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from src.features.draft_assistant.tools import ToolSpec


@dataclass(frozen=True)
class ProgressEvent:
    """Something worth showing the user while a question is still running.

    A question spends its 10-20 seconds in tool rounds, not in writing the
    answer, so "consultando buscar_jugadores…" as it happens is most of the
    perceived wait. ``kind`` is "tool" for now; the shape leaves room for
    token streaming later without changing the contract.
    """

    kind: Literal["tool"]
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


ProgressCallback = Callable[[ProgressEvent], Awaitable[None]]


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ToolCallTrace:
    """One tool the model actually invoked, surfaced to the UI for transparency."""

    name: str
    arguments: dict[str, Any]


@dataclass
class AssistantReply:
    text: str
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    # True when the iteration cap stopped the loop before the model answered.
    truncated: bool = False
    # Which backend and model actually answered. Filled in by the service, since
    # the chat picks both per question.
    provider: str = ""
    model: str = ""


class AssistantProvider(Protocol):
    name: str
    model: str

    async def run(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        on_progress: ProgressCallback | None = None,
    ) -> AssistantReply: ...
