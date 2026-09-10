"""What the consumption line has to say, and how fast the quick mode should be.

First real V2 answer in production: 77 s, 5 tools, 29,515 tokens in, 3,405
out. The output figure vindicated the raised budget (the old cap was 2,000).
The input figure is not the bill, though: both providers reuse cached
prefixes and report those separately, and V2 only read the total. And 77 s is
half a pick clock — gpt-5 thinking at default effort on a question the admin
marked "Rápido".
"""

import httpx
import pytest

from ..config import AssistantSettings
from ..providers import Gateway, parse_turn


def test_openai_cached_tokens_are_read() -> None:
    turn = parse_turn(
        "openai",
        {
            "output": [],
            "usage": {"input_tokens": 5000, "input_tokens_details": {"cached_tokens": 3200}},
        },
    )
    assert turn.input_tokens == 5000 and turn.cached_tokens == 3200


def test_anthropic_cached_tokens_are_read() -> None:
    turn = parse_turn(
        "anthropic",
        {"content": [], "usage": {"input_tokens": 800, "cache_read_input_tokens": 4100}},
    )
    assert turn.cached_tokens == 4100


def test_missing_cache_details_are_zero_not_a_crash() -> None:
    assert parse_turn("openai", {"output": [], "usage": {"input_tokens": 10}}).cached_tokens == 0
    assert parse_turn("openai", {"output": []}).cached_tokens == 0


def test_quick_mode_asks_openai_for_low_effort() -> None:
    payload = Gateway(httpx.AsyncClient(), "openai", "gpt-5", effort="low").payload("s", [])
    assert payload["reasoning"] == {"effort": "low"}


def test_detailed_mode_leaves_effort_to_the_provider() -> None:
    payload = Gateway(httpx.AsyncClient(), "openai", "gpt-5").payload("s", [])
    assert "reasoning" not in payload


def test_anthropic_never_gets_the_openai_knob() -> None:
    payload = Gateway(httpx.AsyncClient(), "anthropic", "m", effort="low").payload("s", [])
    assert "reasoning" not in payload


def test_the_quick_effort_is_configurable_and_can_be_switched_off() -> None:
    assert AssistantSettings().quick_effort == "low"
    assert AssistantSettings(quick_effort="").quick_effort == ""


@pytest.mark.parametrize("value", ["low", "medium", "high", ""])
def test_only_known_efforts_are_accepted(value: str) -> None:
    assert AssistantSettings(quick_effort=value).quick_effort == value


def test_an_unknown_effort_is_rejected() -> None:
    with pytest.raises(ValueError):
        AssistantSettings(quick_effort="turbo")
