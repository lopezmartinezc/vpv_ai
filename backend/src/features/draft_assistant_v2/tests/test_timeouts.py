"""Time budgets sized for a reasoning model, and a timeout that says so.

A single gpt-5 call with an 8k output budget runs 30-60s: it thinks before it
writes. The original 25s per call and 55s total were sized for a chat model
and would have been the next production failure after the token budget.

The frontend aborts at 190s and nginx's /api read timeout is 300s, so the
backend total has to stay under the former with a margin.
"""

from unittest.mock import AsyncMock

import pytest

from .. import history, service
from ..config import AssistantSettings
from ..engine import STOP_TIMEOUT
from ..schemas import History
from .factories import request, snapshot

FRONTEND_ABORT_SECONDS = 190  # use-question.ts


def test_a_provider_call_may_take_as_long_as_reasoning_needs() -> None:
    assert AssistantSettings().provider_timeout_seconds >= 60


def test_the_total_fits_several_reasoning_calls() -> None:
    config = AssistantSettings()
    assert config.timeout_seconds >= 2 * config.provider_timeout_seconds - 30


def test_the_total_stays_under_the_browser_abort() -> None:
    assert AssistantSettings().timeout_seconds < FRONTEND_ABORT_SECONDS - 20


@pytest.mark.asyncio
async def test_a_timeout_is_reported_as_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not a bare "incompleto": the fix for this one is a different setting
    than the fix for a truncated answer, and the admin has to tell them apart."""
    monkeypatch.setattr(service, "load_snapshot", AsyncMock(return_value=snapshot()))
    monkeypatch.setattr(history, "read_history", AsyncMock(return_value=History()))
    monkeypatch.setattr(service, "run_engine", AsyncMock(side_effect=TimeoutError()))
    result = await service.analyze(1, 11, request(), AsyncMock())
    assert result.status == "incomplete"
    assert result.usage.stop_reason == STOP_TIMEOUT
    assert any("tiempo" in w.lower() for w in result.warnings)
