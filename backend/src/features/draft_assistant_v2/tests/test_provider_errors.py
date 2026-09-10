"""Provider errors retain safe status diagnostics, never arbitrary upstream bodies."""

import logging

import httpx
import pytest

from ..errors import AssistantError
from ..providers import Gateway


@pytest.mark.asyncio
async def test_status_is_logged_without_upstream_body(caplog: pytest.LogCaptureFixture) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Unknown parameter: 'foo'"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING), pytest.raises(AssistantError):
            await Gateway(client, "openai", "m").request("s", [{"role": "user", "content": "q"}])
    assert "400" in caplog.text
    assert "Unknown parameter" not in caplog.text


@pytest.mark.asyncio
async def test_the_user_still_gets_a_safe_message(caplog: pytest.LogCaptureFixture) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="stack trace with secret token sk-123")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AssistantError) as exc:
            await Gateway(client, "openai", "m").request("s", [{"role": "user", "content": "q"}])
    assert "sk-123" not in exc.value.message
