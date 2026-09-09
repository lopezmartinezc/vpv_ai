"""Both providers must drive the same tool loop to the same result.

The loop is the part most likely to be subtly wrong (ids that must match, the
echo of assistant turns, termination) and it is pure logic, so it is tested
against fake SDK clients — no network, no API key.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from src.features.draft_assistant.providers.anthropic_provider import AnthropicProvider
from src.features.draft_assistant.providers.base import ChatMessage
from src.features.draft_assistant.providers.openai_provider import OpenAIProvider
from src.features.draft_assistant.tools import ToolSpec

TOOL_CALLS: list[dict[str, Any]] = []


def _tools() -> list[ToolSpec]:
    async def handler(**kwargs: Any) -> str:
        TOOL_CALLS.append(kwargs)
        return "Lewandowski | DEL | Barcelona | Prio 214.5"

    return [
        ToolSpec(
            name="buscar_jugadores",
            description="Busca jugadores.",
            parameters={
                "type": "object",
                "properties": {"posicion": {"type": "string"}},
                "required": [],
            },
            handler=handler,
        )
    ]


@pytest.fixture(autouse=True)
def _reset() -> None:
    TOOL_CALLS.clear()


# --------------------------------------------------------------------------
# Anthropic
# --------------------------------------------------------------------------


class _FakeAnthropic:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        return self._responses.pop(0)


def _anthropic_tool_use() -> Any:
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="buscar_jugadores",
                input={"posicion": "DEL"},
            )
        ],
    )


def _anthropic_text(text: str) -> Any:
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=text)],
    )


@pytest.mark.asyncio
async def test_anthropic_runs_tool_and_returns_final_text() -> None:
    client = _FakeAnthropic([_anthropic_tool_use(), _anthropic_text("Coge a Lewandowski.")])
    provider = AnthropicProvider(client=client, model="claude-opus-5")

    reply = await provider.run(
        system="reglas",
        messages=[ChatMessage(role="user", content="¿mejor delantero?")],
        tools=_tools(),
    )

    assert reply.text == "Coge a Lewandowski."
    assert TOOL_CALLS == [{"posicion": "DEL"}]
    assert [t.name for t in reply.tool_calls] == ["buscar_jugadores"]

    # The tool result must be fed back keyed to the SAME id the model issued,
    # otherwise the API rejects the turn.
    second = client.requests[1]
    tool_result = second["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "toolu_1"
    assert "Lewandowski" in tool_result["content"]


@pytest.mark.asyncio
async def test_anthropic_without_tool_use_answers_directly() -> None:
    client = _FakeAnthropic([_anthropic_text("Hola.")])
    provider = AnthropicProvider(client=client, model="claude-opus-5")

    reply = await provider.run(
        system="reglas", messages=[ChatMessage(role="user", content="hola")], tools=_tools()
    )

    assert reply.text == "Hola."
    assert TOOL_CALLS == []
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_anthropic_caches_the_system_prompt() -> None:
    """Without the cache breakpoint every question repays the full rules prompt."""
    client = _FakeAnthropic([_anthropic_text("ok")])
    provider = AnthropicProvider(client=client, model="claude-opus-5")

    await provider.run(
        system="reglas", messages=[ChatMessage(role="user", content="hola")], tools=_tools()
    )

    system = client.requests[0]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_anthropic_stops_at_the_iteration_cap() -> None:
    """A model stuck in a tool loop must not bleed tokens forever."""
    client = _FakeAnthropic([_anthropic_tool_use() for _ in range(10)])
    provider = AnthropicProvider(client=client, model="claude-opus-5", max_iterations=3)

    reply = await provider.run(
        system="reglas", messages=[ChatMessage(role="user", content="?")], tools=_tools()
    )

    assert len(client.requests) == 3
    assert reply.truncated is True


# --------------------------------------------------------------------------
# OpenAI
# --------------------------------------------------------------------------


class _FakeOpenAI:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        return self._responses.pop(0)


class _FakeFunctionCall:
    type = "function_call"

    def __init__(self) -> None:
        self.call_id = "call_1"
        self.name = "buscar_jugadores"
        self.arguments = json.dumps({"posicion": "DEL"})

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {
            "type": "function_call",
            "call_id": self.call_id,
            "name": self.name,
            "arguments": self.arguments,
        }


def _openai_tool_use() -> Any:
    return SimpleNamespace(output=[_FakeFunctionCall()], output_text="")


def _openai_text(text: str) -> Any:
    return SimpleNamespace(output=[], output_text=text)


@pytest.mark.asyncio
async def test_openai_runs_tool_and_returns_final_text() -> None:
    client = _FakeOpenAI([_openai_tool_use(), _openai_text("Coge a Lewandowski.")])
    provider = OpenAIProvider(client=client, model="gpt-5")

    reply = await provider.run(
        system="reglas",
        messages=[ChatMessage(role="user", content="¿mejor delantero?")],
        tools=_tools(),
    )

    assert reply.text == "Coge a Lewandowski."
    assert TOOL_CALLS == [{"posicion": "DEL"}]
    assert [t.name for t in reply.tool_calls] == ["buscar_jugadores"]

    # Responses API: the result goes back as a function_call_output keyed by
    # call_id, and the assistant's own function_call must be echoed first.
    second_input = client.requests[1]["input"]
    assert second_input[-2]["type"] == "function_call"
    assert second_input[-1] == {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": "Lewandowski | DEL | Barcelona | Prio 214.5",
    }


@pytest.mark.asyncio
async def test_openai_without_tool_use_answers_directly() -> None:
    client = _FakeOpenAI([_openai_text("Hola.")])
    provider = OpenAIProvider(client=client, model="gpt-5")

    reply = await provider.run(
        system="reglas", messages=[ChatMessage(role="user", content="hola")], tools=_tools()
    )

    assert reply.text == "Hola."
    assert TOOL_CALLS == []
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_openai_sends_system_as_instructions() -> None:
    client = _FakeOpenAI([_openai_text("ok")])
    provider = OpenAIProvider(client=client, model="gpt-5")

    await provider.run(
        system="reglas", messages=[ChatMessage(role="user", content="hola")], tools=_tools()
    )

    assert client.requests[0]["instructions"] == "reglas"


@pytest.mark.asyncio
async def test_openai_stops_at_the_iteration_cap() -> None:
    client = _FakeOpenAI([_openai_tool_use() for _ in range(10)])
    provider = OpenAIProvider(client=client, model="gpt-5", max_iterations=3)

    reply = await provider.run(
        system="reglas", messages=[ChatMessage(role="user", content="?")], tools=_tools()
    )

    assert len(client.requests) == 3
    assert reply.truncated is True
