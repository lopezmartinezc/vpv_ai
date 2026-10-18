from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.shared.assistant.providers.openai_provider import OpenAIProvider


@pytest.mark.parametrize("text", ["", "Respuesta parcial"])
async def test_incomplete_is_never_reported_as_complete(text: str) -> None:
    response = SimpleNamespace(
        status="incomplete",
        output_text=text,
        output=[],
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=response)))
    reply = await OpenAIProvider(client, "gpt-5").run(system="s", messages=[], tools=[])
    assert reply.truncated
    assert reply.text.strip()
    if text:
        assert reply.text == text


async def test_incomplete_tool_arguments_are_not_executed() -> None:
    call = SimpleNamespace(type="function_call", name="invalid", arguments="{", call_id="c")
    response = SimpleNamespace(
        status="incomplete",
        output_text="",
        output=[call],
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=response)))
    reply = await OpenAIProvider(client, "gpt-5").run(system="s", messages=[], tools=[])
    assert reply.truncated
    assert reply.tool_calls == []
    client.responses.create.assert_awaited_once()
