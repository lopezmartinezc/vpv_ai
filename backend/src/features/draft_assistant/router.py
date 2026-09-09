from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.core.rate_limit import limiter
from src.features.draft_assistant.providers.base import ChatMessage
from src.features.draft_assistant.service import DraftAssistantService
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/draft-assistant", tags=["draft-assistant"])


class AssistantMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class AssistantAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=20)


class AssistantToolCall(BaseModel):
    name: str
    arguments: dict[str, object]


class AssistantAskResponse(BaseModel):
    reply: str
    provider: str
    tool_calls: list[AssistantToolCall]
    truncated: bool


@router.post("/{season_id}/{phase}/ask", response_model=AssistantAskResponse)
@limiter.limit("30/hour")
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
    )
    return AssistantAskResponse(
        reply=reply.text,
        provider=settings.assistant_provider,
        tool_calls=[
            AssistantToolCall(name=t.name, arguments=t.arguments) for t in reply.tool_calls
        ],
        truncated=reply.truncated,
    )
