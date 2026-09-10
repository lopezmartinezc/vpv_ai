"""Prompt caching on Anthropic, as V1 already does.

System prompt, tool definitions and the bootstrap evidence are identical on
every round of a question; with up to twenty rounds that prefix is resent
twenty times. V1 marks it ephemeral and measured roughly a 4x saving on
input. OpenAI's Responses API caches long prefixes on its own; Anthropic needs
the markers.
"""

import json
from typing import Any

import httpx
from pydantic import JsonValue

from ..providers import Gateway


def _anthropic_payload(messages: list[dict[str, JsonValue]]) -> Any:
    # Round-tripped through JSON on purpose: the assertions are about what
    # goes over the wire, and it keeps them free of JsonValue union indexing.
    payload = Gateway(httpx.AsyncClient(), "anthropic", "m").payload("rules", messages)
    return json.loads(json.dumps(payload))


def test_system_and_tools_are_cache_marked_for_anthropic() -> None:
    payload = _anthropic_payload([{"role": "user", "content": "q"}])
    system = payload["system"]
    assert isinstance(system, list) and system[0]["cache_control"] == {"type": "ephemeral"}
    tools = payload["tools"]
    assert isinstance(tools, list) and tools[-1]["cache_control"] == {"type": "ephemeral"}
    assert all("cache_control" not in t for t in tools[:-1])


def test_the_last_message_is_cache_marked_so_each_round_reuses_the_previous() -> None:
    payload = _anthropic_payload([{"role": "user", "content": "q"}])
    last = payload["messages"][-1]
    assert isinstance(last["content"], list)
    assert last["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert last["content"][-1]["text"] == "q"


def test_block_content_gets_the_marker_on_its_last_block_only() -> None:
    results: list[JsonValue] = [
        {"type": "tool_result", "tool_use_id": "a", "content": "1"},
        {"type": "tool_result", "tool_use_id": "b", "content": "2"},
    ]
    payload = _anthropic_payload(
        [{"role": "user", "content": "q"}, {"role": "user", "content": results}]
    )
    blocks = payload["messages"][-1]["content"]
    assert "cache_control" not in blocks[0]
    assert blocks[-1]["cache_control"] == {"type": "ephemeral"}


def test_the_caller_messages_are_not_mutated() -> None:
    messages: list[dict[str, JsonValue]] = [{"role": "user", "content": "q"}]
    _anthropic_payload(messages)
    assert messages == [{"role": "user", "content": "q"}]


def test_openai_payload_carries_no_anthropic_markers() -> None:
    payload = Gateway(httpx.AsyncClient(), "openai", "m").payload(
        "rules", [{"role": "user", "content": "q"}]
    )
    assert "cache_control" not in json.dumps(payload)
