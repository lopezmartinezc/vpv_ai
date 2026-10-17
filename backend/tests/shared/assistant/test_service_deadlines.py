import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.features.draft_assistant import service as draft_service
from src.features.lineup_assistant import service as lineup_service
from src.shared.assistant import backends
from src.shared.assistant.execution import _reset_budget


@pytest.fixture
def budget_provider(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.setattr(settings, "assistant_timeout_seconds", 0.01)
    monkeypatch.setattr(settings, "assistant_request_timeout_seconds", 1)
    monkeypatch.setattr(settings, "openai_api_key", "test")
    backends._MODELS_CACHE.clear()
    _reset_budget()

    async def slow(provider: str, key: str) -> list[str]:
        await asyncio.sleep(1)
        return ["gpt-5-mini"]

    monkeypatch.setattr(backends, "_vendor_model_ids", slow)
    provider = SimpleNamespace(name="openai", model="gpt-5-mini", run=AsyncMock())
    monkeypatch.setattr(lineup_service, "build_provider", lambda *_: provider)
    monkeypatch.setattr(draft_service, "build_provider", lambda *_: provider)
    return provider


@pytest.mark.parametrize("kind", ["draft", "lineup"])
async def test_service_budget_covers_catalogue(
    kind: str, budget_provider: SimpleNamespace
) -> None:
    session = AsyncMock(spec=AsyncSession)
    with pytest.raises(BusinessRuleError, match="tardado"):
        if kind == "lineup":
            await lineup_service.LineupAssistantService(session).ask(
                season_id=1,
                matchday=1,
                user_id=1,
                question="q",
                provider_name="openai",
                model="gpt-5-mini",
            )
        else:
            await draft_service.DraftAssistantService(session).ask(
                season_id=1,
                phase="preseason",
                user_id=1,
                question="q",
                provider_name="openai",
                model="gpt-5-mini",
            )
    budget_provider.run.assert_not_awaited()
