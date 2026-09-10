"""A stable prompt_cache_key per draft state, so OpenAI routes repeat prefixes
to the machine that already holds them.

Measured twice in production: two consecutive questions at one pick, byte-
identical prefixes (verified by building both requests from the real code
and diffing them), and not one token reused across them - every round within
a question hits, the first round of the next question never does. OpenAI
routes by a hash of the prefix that influences placement rather than fixing
it; within a question the rounds share one live connection, each new
question opens a new one. prompt_cache_key is the documented lever to pin
the routing. It changes exactly when the draft state does, same as the
prefix itself, so a stale cache can never be steered to.
"""

import httpx

from ..providers import Gateway
from ..service import cache_key
from .factories import pick, snapshot


def test_the_key_is_stable_for_the_same_state_and_moves_with_it() -> None:
    same = cache_key(1, snapshot())
    assert same == cache_key(1, snapshot())
    changed = snapshot()
    changed.draft.picks = [pick()]
    assert cache_key(1, changed) != same
    assert cache_key(2, snapshot()) != same  # another draft, another key


def test_openai_payload_carries_the_key() -> None:
    gateway = Gateway(httpx.AsyncClient(), "openai", "gpt-5", cache_key="vpv-v2-1-abc")
    assert gateway.payload("s", [])["prompt_cache_key"] == "vpv-v2-1-abc"


def test_no_key_means_no_field() -> None:
    assert "prompt_cache_key" not in Gateway(httpx.AsyncClient(), "openai", "gpt-5").payload(
        "s", []
    )


def test_anthropic_never_gets_it() -> None:
    gateway = Gateway(httpx.AsyncClient(), "anthropic", "m", cache_key="vpv-v2-1-abc")
    assert "prompt_cache_key" not in gateway.payload("s", [])
