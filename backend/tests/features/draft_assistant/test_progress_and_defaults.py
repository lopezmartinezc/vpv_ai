"""Live progress while the assistant works, and the configured defaults.

A question takes two or three tool rounds and 10-20 seconds. Without progress
events the panel is a mute spinner for all of it; with them the user sees
which tool is being consulted as it happens, which is most of the perceived
wait.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from src.core.config import Settings
from src.features.draft_assistant.providers.anthropic_provider import AnthropicProvider
from src.features.draft_assistant.providers.base import ChatMessage, ProgressEvent
from src.features.draft_assistant.providers.openai_provider import OpenAIProvider
from src.features.draft_assistant.service import sse_line
from src.features.draft_assistant.tools import ToolSpec


def _tool() -> ToolSpec:
    async def handler(**_: Any) -> str:
        return "ok"

    return ToolSpec(
        name="buscar_jugadores",
        description="d",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
    )


# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------


def test_openai_is_the_default_provider() -> None:
    # Built from scratch so the developer's own .env cannot mask the default.
    assert Settings(_env_file=None).assistant_provider == "openai"


# --------------------------------------------------------------------------
# Progress events
# --------------------------------------------------------------------------


class _Anthropic:
    def __init__(self) -> None:
        self.messages = SimpleNamespace(create=self._create)
        self._n = 0

    async def _create(self, **_: Any) -> Any:
        self._n += 1
        if self._n == 1:
            return SimpleNamespace(
                stop_reason="tool_use",
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        id="t1",
                        name="buscar_jugadores",
                        input={"posicion": "DEL"},
                    )
                ],
            )
        return SimpleNamespace(
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Listo.")]
        )


class _Call:
    type = "function_call"
    call_id = "c1"
    name = "buscar_jugadores"
    arguments = json.dumps({"posicion": "DEL"})

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {
            "type": "function_call",
            "call_id": "c1",
            "name": self.name,
            "arguments": self.arguments,
        }


class _OpenAI:
    def __init__(self) -> None:
        self.responses = SimpleNamespace(create=self._create)
        self._n = 0

    async def _create(self, **_: Any) -> Any:
        self._n += 1
        if self._n == 1:
            return SimpleNamespace(output=[_Call()], output_text="")
        return SimpleNamespace(output=[], output_text="Listo.")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "make",
    [
        lambda: AnthropicProvider(client=_Anthropic(), model="m"),
        lambda: OpenAIProvider(client=_OpenAI(), model="m"),
    ],
    ids=["anthropic", "openai"],
)
async def test_each_tool_call_is_reported_as_it_happens(make: Any) -> None:
    seen: list[ProgressEvent] = []

    async def on_progress(event: ProgressEvent) -> None:
        seen.append(event)

    reply = await make().run(
        system="s",
        messages=[ChatMessage("user", "?")],
        tools=[_tool()],
        on_progress=on_progress,
    )

    assert reply.text == "Listo."
    assert [e.kind for e in seen] == ["tool"]
    assert seen[0].name == "buscar_jugadores"
    assert seen[0].arguments == {"posicion": "DEL"}


@pytest.mark.asyncio
async def test_progress_is_optional() -> None:
    """The plain JSON endpoint keeps working without a callback."""
    reply = await AnthropicProvider(client=_Anthropic(), model="m").run(
        system="s", messages=[ChatMessage("user", "?")], tools=[_tool()]
    )
    assert reply.text == "Listo."


# --------------------------------------------------------------------------
# SSE framing
# --------------------------------------------------------------------------


def test_sse_line_is_one_event_per_line_with_json_data() -> None:
    line = sse_line("tool", {"name": "buscar_jugadores"})
    assert line == 'event: tool\ndata: {"name": "buscar_jugadores"}\n\n'


def test_sse_line_never_breaks_the_frame_on_newlines_in_text() -> None:
    """A newline inside the JSON would end the SSE frame early; json.dumps
    escapes it, so multi-line replies arrive intact."""
    line = sse_line("done", {"reply": "línea 1\nlínea 2"})
    assert line.count("\n\n") == 1
    assert "\\n" in line
