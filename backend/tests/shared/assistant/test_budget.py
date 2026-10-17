"""What one question may cost, and which models it may ask.

The chats had a cap on tool rounds and nothing else: no limit on the
answer's length, no deadline for the whole turn, no cap on how many
questions run at once, and any model id of the right shape went through
to the vendor. Now the answer is bounded in tokens, the turn in seconds,
the questions in flight in number, and the model has to be one the vendor
listed (or the configured default).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.shared.assistant import backends
from src.shared.assistant.backends import answer, build_provider, ensure_model_offered, list_models
from src.shared.assistant.providers.base import AssistantReply


@pytest.fixture
def keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "openai_api_key", "sk-oai-test")
    monkeypatch.setattr(settings, "assistant_openai_model", "gpt-5")
    monkeypatch.setattr(settings, "assistant_anthropic_model", "claude-opus-5")
    backends._MODELS_CACHE.clear()


def vendor(ids: dict[str, list[str]]) -> Any:
    async def fake(provider: str, key: str) -> list[str]:
        return ids.get(provider, [])

    return fake


# --- catalogue ---------------------------------------------------------------


async def test_the_dropdown_offers_the_vendor_list_default_first(
    keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", vendor({"openai": ["gpt-5-mini", "gpt-5"]}))
    assert await list_models("openai") == ["gpt-5", "gpt-5-mini"]


async def test_a_default_the_vendor_does_not_list_is_not_offered(
    keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", vendor({"openai": ["gpt-5-mini"]}))
    assert await list_models("openai") == ["gpt-5-mini"]


async def test_without_a_vendor_list_the_default_is_all_there_is(
    keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", vendor({}))
    assert await list_models("openai") == ["gpt-5"]


async def test_a_model_the_vendor_did_not_list_is_refused(
    keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", vendor({"openai": ["gpt-5", "gpt-5-mini"]}))
    await ensure_model_offered("openai", "gpt-5-mini")
    await ensure_model_offered("openai", None)
    with pytest.raises(BusinessRuleError, match="no disponible"):
        await ensure_model_offered("openai", "gpt-9-astra")


async def test_the_configured_default_is_always_allowed(
    keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", vendor({"openai": ["gpt-5-mini"]}))
    await ensure_model_offered("openai", "gpt-5")


async def test_without_a_vendor_list_only_the_default_is_allowed(
    keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", vendor({}))
    await ensure_model_offered("openai", "gpt-5")
    with pytest.raises(BusinessRuleError, match="no disponible"):
        await ensure_model_offered("openai", "gpt-5-mini")


# --- budgets -----------------------------------------------------------------


def test_providers_are_built_with_the_output_budget_and_request_timeout(
    keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "assistant_max_output_tokens", 1234)
    monkeypatch.setattr(settings, "assistant_request_timeout_seconds", 7.0)
    oai = build_provider("openai")
    ant = build_provider("anthropic")
    assert oai._max_output_tokens == 1234
    assert ant._max_tokens == 1234
    assert oai._client.timeout == 7.0
    assert ant._client.timeout == 7.0


class Slow:
    name = "fake"
    model = "fake-1"

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    async def run(self, **kwargs: Any) -> AssistantReply:
        await asyncio.sleep(self.seconds)
        return AssistantReply(text="ok")


async def test_a_turn_that_overruns_the_deadline_is_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "assistant_timeout_seconds", 0.05)
    with pytest.raises(BusinessRuleError, match="tardado"):
        await answer(Slow(1.0), system="s", messages=[], tools=[])


async def test_a_turn_within_the_deadline_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "assistant_timeout_seconds", 1.0)
    reply = await answer(Slow(0.0), system="s", messages=[], tools=[])
    assert reply.text == "ok"


async def test_one_question_too_many_is_told_to_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "assistant_timeout_seconds", 5.0)
    monkeypatch.setattr(settings, "assistant_max_concurrent", 1)
    backends._reset_budget()
    first = asyncio.create_task(answer(Slow(0.2), system="s", messages=[], tools=[]))
    await asyncio.sleep(0.01)
    with pytest.raises(BusinessRuleError, match="ocupado"):
        await answer(Slow(0.0), system="s", messages=[], tools=[])
    assert (await first).text == "ok"
    # The slot is free again afterwards.
    assert (await answer(Slow(0.0), system="s", messages=[], tools=[])).text == "ok"
