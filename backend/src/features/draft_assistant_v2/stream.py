from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import suppress

from pydantic import JsonValue

from .engine import Progress
from .errors import AssistantError
from .schemas import Answer

logger = logging.getLogger(__name__)


def frame(event: str, data: dict[str, JsonValue]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def events(work: Callable[[Progress], Awaitable[Answer]]) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)

    async def progress(name: str) -> None:
        await queue.put(frame("progress", {"name": name}))

    task = asyncio.create_task(produce(work, progress, queue))
    try:
        while not task.done() or not queue.empty():
            try:
                yield await asyncio.wait_for(queue.get(), timeout=1)
            except TimeoutError:
                yield ": heartbeat\n\n"
        await task
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def produce(
    work: Callable[[Progress], Awaitable[Answer]], progress: Progress, queue: asyncio.Queue[str]
) -> None:
    try:
        result = await work(progress)
        await queue.put(frame("done", result.model_dump(mode="json")))
    except AssistantError as exc:
        await queue.put(frame("error", {"code": exc.code, "message": exc.message}))
    except TimeoutError:
        await queue.put(
            frame("error", {"code": "TIMEOUT", "message": "Se agotó el tiempo. Reintenta."})
        )
    except Exception:
        logger.error("assistant_v2 request failed")
        await queue.put(
            frame(
                "error",
                {
                    "code": "ASSISTANT_FAILED",
                    "message": "No se pudo completar la consulta. Reintenta.",
                },
            )
        )
