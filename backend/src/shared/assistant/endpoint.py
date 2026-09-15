"""What every chat endpoint does the same way: who asks, and the SSE stream."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi.responses import StreamingResponse

from src.core.exceptions import BusinessRuleError
from src.shared.assistant.backends import sse_line
from src.shared.assistant.providers.base import AssistantReply, ProgressCallback, ProgressEvent

logger = logging.getLogger(__name__)


def asker_id(user: dict) -> int:
    """The asker's id, from the JWT. The chat must know who it is talking to:
    "my squad" has to answer about them."""
    try:
        return int(user.get("sub") or 0)
    except (TypeError, ValueError):
        return 0


def reply_payload(reply: AssistantReply) -> dict[str, object]:
    return {
        "reply": reply.text,
        "provider": reply.provider,
        "model": reply.model,
        "tool_calls": [{"name": t.name, "arguments": t.arguments} for t in reply.tool_calls],
        "truncated": reply.truncated,
    }


def stream_answer(
    ask: Callable[[ProgressCallback], Awaitable[AssistantReply]], label: str
) -> StreamingResponse:
    """Answer over Server-Sent Events: one ``tool`` event per tool call as it
    happens, then a single ``done`` with the full reply, or ``error``.

    A question spends its seconds in tool rounds, so saying what is being
    consulted is most of the perceived wait. The text itself is not streamed
    token by token: with tools in the loop that would save little and cost a
    provider-specific code path each.
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def on_progress(event: ProgressEvent) -> None:
        await queue.put(sse_line(event.kind, {"name": event.name, "arguments": event.arguments}))

    async def worker() -> None:
        try:
            reply = await ask(on_progress)
            await queue.put(sse_line("done", reply_payload(reply)))
        except BusinessRuleError as exc:
            await queue.put(sse_line("error", {"message": exc.message}))
        except Exception:
            logger.exception("%s: stream failed", label)
            await queue.put(sse_line("error", {"message": "El asistente ha fallado."}))
        finally:
            await queue.put(None)

    async def body() -> AsyncIterator[str]:
        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
