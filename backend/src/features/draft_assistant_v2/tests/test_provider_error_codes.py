"""Log the provider's structured error fields, never its free text.

Dropping the body entirely was right about the risk - an upstream message can
echo request content - and cost the diagnosis: a 400 for a rejected parameter
and a 400 for a malformed message look identical from the status alone. The
providers return a structured error object beside the prose; type, code and
the offending parameter name are field identifiers, not content.
"""

import logging

import httpx
import pytest

from ..errors import AssistantError
from ..providers import Gateway


async def _fail(client: httpx.AsyncClient) -> None:
    with pytest.raises(AssistantError):
        await Gateway(client, "openai", "m").request("s", [{"role": "user", "content": "q"}])


@pytest.mark.asyncio
async def test_structured_error_fields_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    body = {
        "error": {
            "type": "invalid_request_error",
            "code": "unknown_parameter",
            "param": "prompt_cache_key",
            "message": "Unknown parameter: 'prompt_cache_key'.",
        }
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING):
            await _fail(client)
    assert "status=400" in caplog.text
    assert "invalid_request_error" in caplog.text
    assert "unknown_parameter" in caplog.text
    assert "prompt_cache_key" in caplog.text


@pytest.mark.asyncio
async def test_the_free_text_message_never_reaches_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The message is where an upstream can echo what we sent."""
    body = {
        "error": {"type": "invalid_request_error", "message": "Bad value: SECRETO DEL USUARIO"}
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING):
            await _fail(client)
    assert "SECRETO DEL USUARIO" not in caplog.text
    assert "invalid_request_error" in caplog.text


@pytest.mark.asyncio
async def test_a_non_json_body_is_not_echoed(caplog: pytest.LogCaptureFixture) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>SECRET_API_KEY sk-abc</html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING):
            await _fail(client)
    assert "status=502" in caplog.text
    assert "SECRET_API_KEY" not in caplog.text and "sk-abc" not in caplog.text


@pytest.mark.asyncio
async def test_anthropic_error_shape_is_read_too(caplog: pytest.LogCaptureFixture) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AssistantError):
            with caplog.at_level(logging.WARNING):
                await Gateway(client, "anthropic", "m").request("s", [])
    assert "overloaded_error" in caplog.text
