import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.shared.assistant.execution import _reset_budget, answer
from src.shared.assistant.providers.base import AssistantReply


async def test_preparation_is_inside_timeout_and_releases_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "assistant_timeout_seconds", 0.01)
    _reset_budget()
    provider = SimpleNamespace(
        name="test", model="m", run=AsyncMock(return_value=AssistantReply("ok"))
    )

    async def prepare() -> None:
        await asyncio.sleep(1)

    with pytest.raises(BusinessRuleError, match="tardado"):
        await answer(provider, system="s", messages=[], tools=[], prepare=prepare)
    provider.run.assert_not_awaited()
    assert (await answer(provider, system="s", messages=[], tools=[])).text == "ok"


async def test_preparation_holds_slot_and_cancel_frees_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "assistant_max_concurrent", 1)
    _reset_budget()
    entered = asyncio.Event()
    provider = SimpleNamespace(
        name="test", model="m", run=AsyncMock(return_value=AssistantReply("ok"))
    )

    async def prepare() -> None:
        entered.set()
        await asyncio.Event().wait()

    pending = asyncio.create_task(
        answer(provider, system="s", messages=[], tools=[], prepare=prepare)
    )
    await asyncio.wait_for(entered.wait(), 1)
    try:
        with pytest.raises(BusinessRuleError, match="ocupado"):
            await answer(provider, system="s", messages=[], tools=[])
    finally:
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    assert (await answer(provider, system="s", messages=[], tools=[])).text == "ok"


async def test_preparation_error_never_calls_provider() -> None:
    _reset_budget()
    provider = SimpleNamespace(name="test", model="m", run=AsyncMock())
    prepare = AsyncMock(side_effect=BusinessRuleError("Modelo no disponible"))
    with pytest.raises(BusinessRuleError, match="Modelo"):
        await answer(provider, system="s", messages=[], tools=[], prepare=prepare)
    provider.run.assert_not_awaited()
