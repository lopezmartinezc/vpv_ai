"""Running out of tool rounds, and recovering from a tool that fails.

Both were hit in production on the very first question ("¿A quién cojo en este
pick?"), which legitimately chains estado_draft -> proximos_turnos -> plantilla
-> escasez_posicional -> buscar_jugadores per position: eight calls, which was
exactly the old cap.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.core.config import settings
from src.features.draft_assistant.board_tools import AssistantContext, build_tools
from src.features.draft_assistant.providers.anthropic_provider import AnthropicProvider
from src.features.draft_assistant.providers.base import ChatMessage
from src.features.draft_assistant.tools import ToolSpec, run_tool


def _tool() -> ToolSpec:
    async def handler(**_: Any) -> str:
        return "ok"

    return ToolSpec(
        name="t",
        description="d",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
    )


class _FakeAnthropic:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        return SimpleNamespace(
            stop_reason="tool_use",
            content=[SimpleNamespace(type="tool_use", id="x", name="t", input={})],
        )


@pytest.mark.asyncio
async def test_the_round_budget_is_configurable() -> None:
    """A broad question needs more than eight rounds; the budget is a setting
    so it can be raised in production without a deploy."""
    client = _FakeAnthropic()
    provider = AnthropicProvider(client=client, model="m", max_iterations=11)

    await provider.run(system="s", messages=[ChatMessage("user", "?")], tools=[_tool()])

    assert len(client.requests) == 11


@pytest.mark.asyncio
async def test_the_default_budget_covers_a_broad_question() -> None:
    """Eight was exactly the number of calls a 'who do I pick?' needs."""
    assert settings.assistant_max_tool_rounds >= 12


@pytest.mark.asyncio
async def test_truncated_reply_names_the_tools_it_managed_to_consult() -> None:
    """Without this the user only sees 'I ran out', with nothing to report."""
    client = _FakeAnthropic()
    provider = AnthropicProvider(client=client, model="m", max_iterations=2)

    reply = await provider.run(
        system="s", messages=[ChatMessage("user", "?")], tools=[_tool()]
    )

    assert reply.truncated is True
    assert "t" in reply.text


class _FailingSession:
    def __init__(self) -> None:
        self.rollbacks = 0

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_a_failing_tool_rolls_the_session_back() -> None:
    """One failed query aborts the transaction; without a rollback EVERY later
    tool fails too, so the model burns its whole budget on errors."""
    session = _FailingSession()
    ctx = AssistantContext(session=session, season_id=1, phase="preseason")  # type: ignore[arg-type]

    async def boom() -> Any:
        raise RuntimeError("relation does not exist")

    ctx.draft = boom  # type: ignore[method-assign]
    ctx.board = boom  # type: ignore[method-assign]

    out = await run_tool(build_tools(ctx), "estado_draft", {})

    assert "error" in out.lower()
    assert session.rollbacks == 1
