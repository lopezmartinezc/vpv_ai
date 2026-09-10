"""Name and size of every tool result, logged per call.

The per-round usage log showed Anthropic caching working exactly as intended
- 12 uncached tokens a round - and, in the same breath, a second round that
wrote 7,290 new tokens. The only new thing in a second round is a tool call
and its result, so one tool answer cost more than the whole initial prompt,
written at a premium and resent on every later round on both providers.
Which tool, the usage log cannot say. This can.
"""

import logging

import pytest

from ..engine import execute_calls
from ..providers import Call, Turn
from ..schemas import Usage, ViewContext
from ..tools import Toolset
from .factories import snapshot


async def _noop(_: str) -> None:
    return None


@pytest.mark.asyncio
async def test_each_tool_result_is_logged_with_its_size(caplog: pytest.LogCaptureFixture) -> None:
    turn = Turn(calls=[Call(id="1", name="plantillas", arguments="{}")])
    with caplog.at_level(logging.INFO):
        await execute_calls(turn, Toolset(snapshot(), 11, ViewContext()), _noop, Usage(), set())
    line = next(r for r in caplog.records if "assistant_v2 tool" in r.getMessage())
    message = line.getMessage()
    assert "name=plantillas" in message
    assert "chars=" in message and "error=False" in message


@pytest.mark.asyncio
async def test_a_rejected_call_is_logged_as_an_error(caplog: pytest.LogCaptureFixture) -> None:
    turn = Turn(calls=[Call(id="1", name="buscar_jugadores", arguments='{"limit":5000}')])
    with caplog.at_level(logging.INFO):
        await execute_calls(turn, Toolset(snapshot(), 11, ViewContext()), _noop, Usage(), set())
    assert any("error=True" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_the_log_carries_counts_not_content(caplog: pytest.LogCaptureFixture) -> None:
    turn = Turn(calls=[Call(id="1", name="detalle_jugador", arguments='{"player_id":1}')])
    with caplog.at_level(logging.INFO):
        await execute_calls(turn, Toolset(snapshot(), 11, ViewContext()), _noop, Usage(), set())
    tool_lines = [r.getMessage() for r in caplog.records if "assistant_v2 tool" in r.getMessage()]
    assert tool_lines and all("Jugador 1" not in m for m in tool_lines)
