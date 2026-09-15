from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.features.lineup_assistant.schemas import (
    LineupAskRequest,
    LineupAskResponse,
    SuggestionResponse,
)
from src.features.lineup_assistant.service import LineupAssistantService
from src.shared.assistant.endpoint import asker_id, reply_payload, stream_answer
from src.shared.assistant.providers.base import AssistantReply, ChatMessage, ProgressCallback
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/lineup-assistant", tags=["lineup-assistant"])


def _require_enabled() -> None:
    if not settings.assistant_enabled:
        raise BusinessRuleError("El asistente esta desactivado")


# Not rate limited, like the draft chat: a question can trigger at most
# ASSISTANT_MAX_TOOL_ROUNDS tool calls, and the money limit belongs on the
# provider console. Season and matchday come from the path and the asker from
# the JWT: the model never chooses whose lineup or which matchday it reads.
async def _ask(
    db: AsyncSession,
    season_id: int,
    matchday: int,
    payload: LineupAskRequest,
    user: dict,
    on_progress: ProgressCallback | None = None,
) -> AssistantReply:
    return await LineupAssistantService(db).ask(
        season_id=season_id,
        matchday=matchday,
        question=payload.question,
        history=[ChatMessage(role=m.role, content=m.content) for m in payload.history],  # type: ignore[arg-type]
        user_id=asker_id(user),
        provider_name=payload.provider,
        model=payload.model,
        on_progress=on_progress,
    )


@router.post("/{season_id}/{matchday}/ask", response_model=LineupAskResponse)
async def ask(
    season_id: int,
    matchday: int,
    payload: LineupAskRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_admin),
) -> LineupAskResponse:
    """Ask the lineup assistant a question. Admin only."""
    _require_enabled()
    reply = await _ask(db, season_id, matchday, payload, user)
    return LineupAskResponse.model_validate(reply_payload(reply))


@router.post("/{season_id}/{matchday}/ask/stream")
async def ask_stream(
    season_id: int,
    matchday: int,
    payload: LineupAskRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_admin),
) -> StreamingResponse:
    """Same question as /ask, answered over Server-Sent Events."""
    _require_enabled()

    async def run(on_progress: ProgressCallback) -> AssistantReply:
        return await _ask(db, season_id, matchday, payload, user, on_progress)

    return stream_answer(run, "lineup_assistant")


@router.get("/{season_id}/{matchday}/suggestion", response_model=SuggestionResponse)
async def suggestion(
    season_id: int,
    matchday: int,
    formacion: str | None = Query(None, pattern=r"^1-\d-\d-\d$"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_admin),
) -> SuggestionResponse:
    """The eleven worth the most for the asker this matchday. Admin only.

    Needs no model: it is the optimizer alone, so it works with the chat off.
    Fills the lineup screen and saves nothing.
    """
    return await LineupAssistantService(db).suggestion(
        season_id=season_id, matchday=matchday, user_id=asker_id(user), formation=formacion
    )
