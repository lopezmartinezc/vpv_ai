"""The provider's raw usage object, logged per round.

The parsed totals summed over rounds cannot say WHERE a cache stops being
reused: a within-question hit on round 2 and a cross-question hit on round 1
add up the same. On Anthropic, three rounds sent ~19,500 tokens and read only
6,122 from cache - the same 6,122 as a run hours earlier - and the totals
alone cannot say whether rounds 2 and 3 are re-reading the fixed block or
reading nothing. One raw object per round can. It is not sensitive: counts,
no content.
"""

import logging

import httpx
import pytest

from ..providers import Gateway


@pytest.mark.asyncio
async def test_raw_usage_is_logged_per_round(caplog: pytest.LogCaptureFixture) -> None:
    usage = {
        "input_tokens": 24,
        "cache_creation_input_tokens": 1200,
        "cache_read_input_tokens": 6122,
        "output_tokens": 210,
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [], "usage": usage})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.INFO):
            await Gateway(client, "anthropic", "m").request(
                "s", [{"role": "user", "content": "q"}]
            )
    assert "assistant_v2 usage" in caplog.text
    assert "6122" in caplog.text and "1200" in caplog.text


@pytest.mark.asyncio
async def test_a_missing_usage_object_is_logged_as_such(caplog: pytest.LogCaptureFixture) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.INFO):
            await Gateway(client, "openai", "gpt-5").request(
                "s", [{"role": "user", "content": "q"}]
            )
    assert "usage=None" in caplog.text


@pytest.mark.asyncio
async def test_the_log_never_carries_content(caplog: pytest.LogCaptureFixture) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [{"type": "message", "content": "SECRET PLAYER NOTE"}],
                "usage": {"input_tokens": 5},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.INFO):
            await Gateway(client, "openai", "gpt-5").request(
                "s", [{"role": "user", "content": "q"}]
            )
    assert "SECRET PLAYER NOTE" not in caplog.text
