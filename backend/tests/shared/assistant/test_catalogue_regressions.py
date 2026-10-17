from unittest.mock import AsyncMock

import pytest

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.shared.assistant import backends


@pytest.fixture(autouse=True)
def catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test")
    monkeypatch.setattr(settings, "assistant_openai_model", "gpt-5")
    backends._MODELS_CACHE.clear()


@pytest.mark.parametrize("model", [None, "gpt-5"])
async def test_absent_default_is_rejected(
    monkeypatch: pytest.MonkeyPatch, model: str | None
) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", AsyncMock(return_value=["gpt-5-mini"]))
    with pytest.raises(BusinessRuleError, match="no disponible"):
        await backends.ensure_model_offered("openai", model)


async def test_successful_empty_list_is_not_an_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", AsyncMock(return_value=[]))
    assert await backends.list_models("openai") == []
    with pytest.raises(BusinessRuleError):
        await backends.ensure_model_offered("openai", None)


async def test_outage_allows_only_configured_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backends, "_vendor_model_ids", AsyncMock(side_effect=TimeoutError))
    assert await backends.list_models("openai") == ["gpt-5"]
    await backends.ensure_model_offered("openai", None)
    with pytest.raises(BusinessRuleError):
        await backends.ensure_model_offered("openai", "gpt-5-mini")


async def test_catalogue_has_its_own_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    monkeypatch.setattr(settings, "assistant_request_timeout_seconds", 0.01)

    async def slow(provider: str, key: str) -> list[str]:
        await asyncio.sleep(1)
        return ["other"]

    monkeypatch.setattr(backends, "_vendor_model_ids", slow)
    assert await asyncio.wait_for(backends.list_models("openai"), 0.5) == ["gpt-5"]


async def test_endpoint_default_is_in_offered_models(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.features.draft_assistant.router import providers

    monkeypatch.setattr(settings, "assistant_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(backends, "_vendor_model_ids", AsyncMock(return_value=["gpt-5-mini"]))
    response = await providers(user={})
    offered = response.providers[0]
    assert offered.default_model == "gpt-5-mini"
    assert offered.default_model in offered.models


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_listing_clients_have_timeout_and_are_closed(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    import importlib
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    monkeypatch.setattr(settings, "assistant_request_timeout_seconds", 3)
    client = AsyncMock()
    client.models.list.return_value = SimpleNamespace(data=[SimpleNamespace(id="gpt-5")])
    manager = AsyncMock()
    manager.__aenter__.return_value = client
    factory = MagicMock(return_value=manager)
    sdk = importlib.import_module(provider)
    monkeypatch.setattr(sdk, "AsyncOpenAI" if provider == "openai" else "AsyncAnthropic", factory)
    assert await backends._vendor_model_ids(provider, "test") == ["gpt-5"]
    factory.assert_called_once_with(api_key="test", timeout=3, max_retries=0)
    manager.__aexit__.assert_awaited_once()
