from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.features.draft_assistant.providers.base import ChatMessage, ProgressEvent
from src.features.draft_assistant.service import (
    DraftAssistantService,
    available_providers,
    clean_setting,
    default_model_for,
    list_models,
    sse_line,
)
from src.features.stats.participation import ParticipationModel
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/draft-assistant", tags=["draft-assistant"])
logger = logging.getLogger(__name__)


def _user_id(user: dict) -> int:
    """The asker's id, from the JWT. The chat must know who it is talking to:
    "de que voy corto?" has to answer about them, not about whoever holds the
    turn."""
    try:
        return int(user.get("sub") or 0)
    except (TypeError, ValueError):
        return 0


class AssistantMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class AssistantAskRequest(BaseModel):
    # Generous rather than tight: these exist so a malformed client cannot post
    # a megabyte, not to ration the conversation.
    question: str = Field(min_length=1, max_length=4000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=80)
    # Which backend answers this question. Null uses ASSISTANT_PROVIDER. The
    # pattern is a first gate; the service validates against the whitelist and
    # checks the key exists.
    provider: str | None = Field(default=None, pattern="^(anthropic|openai)$")
    # Null uses the provider's configured default model.
    model: str | None = Field(default=None, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")
    # Which participation model the board on the admin's screen is using, so
    # the chat quotes the same Prioridad he is looking at.
    participacion: ParticipationModel = ParticipationModel.MIXTO


class ProviderInfo(BaseModel):
    name: str
    models: list[str]
    default_model: str


class AssistantProvidersResponse(BaseModel):
    """What the chat's selectors should offer. Names only, never keys."""

    providers: list[ProviderInfo]
    default: str


class AssistantToolCall(BaseModel):
    name: str
    arguments: dict[str, object]


class AssistantAskResponse(BaseModel):
    reply: str
    provider: str
    model: str
    tool_calls: list[AssistantToolCall]
    truncated: bool


# Deliberately NOT rate limited: during a draft the admin asks as often as he
# needs to, and a cap that trips mid-pick is worse than the spend it prevents.
# The app registers no SlowAPIMiddleware, so with no decorator here there is no
# limit at all - the global default_limits never apply to undecorated routes.
# The runaway-cost guard that remains is per QUESTION, not per session: a
# question can trigger at most ASSISTANT_MAX_TOOL_ROUNDS tool calls. Put a spend
# cap on the provider console; that is the right place for a money limit.
@router.post("/{season_id}/{phase}/ask", response_model=AssistantAskResponse)
async def ask(
    request: Request,
    season_id: int,
    phase: str,
    payload: AssistantAskRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_admin),
) -> AssistantAskResponse:
    """Ask the draft assistant a question. Admin only.

    ``season_id`` and ``phase`` come from the path and are handed to the tools
    by the service — the model can never choose which season or draft it reads.
    """
    if not settings.assistant_enabled:
        raise BusinessRuleError("El asistente de draft esta desactivado")

    reply = await DraftAssistantService(db).ask(
        season_id=season_id,
        phase=phase,
        question=payload.question,
        history=[ChatMessage(role=m.role, content=m.content) for m in payload.history],  # type: ignore[arg-type]
        user_id=_user_id(user),
        provider_name=payload.provider,
        model=payload.model,
        participation_model=payload.participacion,
    )
    return AssistantAskResponse(
        reply=reply.text,
        provider=reply.provider,
        model=reply.model,
        tool_calls=[
            AssistantToolCall(name=t.name, arguments=t.arguments) for t in reply.tool_calls
        ],
        truncated=reply.truncated,
    )


@router.post("/{season_id}/{phase}/ask/stream")
async def ask_stream(
    request: Request,
    season_id: int,
    phase: str,
    payload: AssistantAskRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_admin),
) -> StreamingResponse:
    """Same question as /ask, answered over Server-Sent Events.

    A question spends its 10-20 seconds in tool rounds. This streams one
    ``tool`` event per call as it happens, then a single ``done`` event with the
    full reply (or ``error``), so the panel can say what it is consulting
    instead of showing a mute spinner. The answer text itself is not streamed
    token by token: with tools in the loop that would save little and cost a
    provider-specific code path each.
    """
    if not settings.assistant_enabled:
        raise BusinessRuleError("El asistente de draft esta desactivado")

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def on_progress(event: ProgressEvent) -> None:
        await queue.put(sse_line(event.kind, {"name": event.name, "arguments": event.arguments}))

    async def worker() -> None:
        try:
            reply = await DraftAssistantService(db).ask(
                season_id=season_id,
                phase=phase,
                question=payload.question,
                history=[ChatMessage(role=m.role, content=m.content) for m in payload.history],  # type: ignore[arg-type]
                user_id=_user_id(user),
                provider_name=payload.provider,
                model=payload.model,
                participation_model=payload.participacion,
                on_progress=on_progress,
            )
            await queue.put(
                sse_line(
                    "done",
                    {
                        "reply": reply.text,
                        "provider": reply.provider,
                        "model": reply.model,
                        "tool_calls": [
                            {"name": t.name, "arguments": t.arguments} for t in reply.tool_calls
                        ],
                        "truncated": reply.truncated,
                    },
                )
            )
        except BusinessRuleError as exc:
            await queue.put(sse_line("error", {"message": exc.message}))
        except Exception:
            logger.exception("draft_assistant: stream failed")
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


@router.get("/providers", response_model=AssistantProvidersResponse)
async def providers(
    user: dict = Depends(get_current_admin),
) -> AssistantProvidersResponse:
    """Backends and models the chat can offer, so the selectors only show what
    works. Model lists come live from each vendor (cached), so a new release
    appears without a deploy."""
    if not settings.assistant_enabled:
        raise BusinessRuleError("El asistente de draft esta desactivado")
    names = available_providers()
    return AssistantProvidersResponse(
        providers=[
            ProviderInfo(
                name=name,
                models=await list_models(name),
                default_model=default_model_for(name),
            )
            for name in names
        ],
        default=clean_setting(settings.assistant_provider).lower(),
    )
