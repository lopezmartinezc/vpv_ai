"""Bound preparation and inference with the same concurrency and time budget."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from src.core.config import settings
from src.core.exceptions import BusinessRuleError

from .providers.base import AssistantProvider, AssistantReply, ChatMessage, ProgressCallback
from .tools import ToolSpec

logger = logging.getLogger(__name__)
_budget: asyncio.Semaphore | None = None
_budget_size = 0


def _reset_budget() -> None:
    global _budget, _budget_size
    _budget, _budget_size = None, 0


def _slots() -> asyncio.Semaphore:
    global _budget, _budget_size
    size = max(1, settings.assistant_max_concurrent)
    if _budget is None or _budget_size != size:
        _budget, _budget_size = asyncio.Semaphore(size), size
    return _budget


@asynccontextmanager
async def _question_budget() -> AsyncIterator[None]:
    slots = _slots()
    if slots.locked():
        raise BusinessRuleError(
            "El asistente esta ocupado con otras preguntas. Prueba en unos segundos."
        )
    async with slots:
        try:
            async with asyncio.timeout(settings.assistant_timeout_seconds):
                yield
        except TimeoutError:
            logger.warning("assistant: question timeout")
            raise BusinessRuleError(
                "El asistente ha tardado demasiado. Prueba una pregunta mas concreta."
            ) from None


async def answer(
    provider: AssistantProvider,
    *,
    system: str,
    messages: Sequence[ChatMessage],
    tools: Sequence[ToolSpec],
    on_progress: ProgressCallback | None = None,
    prepare: Callable[[], Awaitable[None]] | None = None,
) -> AssistantReply:
    started = time.monotonic()
    async with _question_budget():
        if prepare is not None:
            await prepare()
        reply = await provider.run(
            system=system, messages=messages, tools=tools, on_progress=on_progress
        )
    logger.info(
        "assistant: provider=%s model=%s elapsed=%.1fs tools=%d truncated=%s",
        provider.name,
        provider.model,
        time.monotonic() - started,
        len(reply.tool_calls),
        reply.truncated,
    )
    return reply
