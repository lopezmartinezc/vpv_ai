"""A provider error must leave a trace an admin can act on.

Every non-2xx came back as "el proveedor no ha podido responder" with the body
discarded. A 400 for a rejected parameter, a 401 for a rotated key and a 529
for an overloaded upstream are three different afternoons, and the response
body is the only thing that tells them apart.
"""

import logging

import httpx
import pytest

from ..errors import AssistantError
from ..providers import Gateway


@pytest.mark.asyncio
async def test_status_and_body_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Unknown parameter: 'foo'"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING), pytest.raises(AssistantError):
            await Gateway(client, "openai", "m").request("s", [{"role": "user", "content": "q"}])
    assert "400" in caplog.text
    assert "Unknown parameter" in caplog.text


@pytest.mark.asyncio
async def test_the_user_still_gets_a_safe_message(caplog: pytest.LogCaptureFixture) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="stack trace with secret token sk-123")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AssistantError) as exc:
            await Gateway(client, "openai", "m").request("s", [{"role": "user", "content": "q"}])
    assert "sk-123" not in exc.value.message
