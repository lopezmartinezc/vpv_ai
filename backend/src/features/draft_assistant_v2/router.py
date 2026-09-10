from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import history, service
from .auth import admin_id
from .config import config
from .errors import AssistantError
from .providers import capabilities, validate_provider
from .schemas import AskRequest, Capabilities, History, Revision
from .stream import events

router = APIRouter(prefix="/draft-assistant-v2", tags=["draft-assistant-v2"])
Admin = Annotated[int, Depends(admin_id)]
DraftId = Annotated[int, Path(gt=0)]


def require_enabled() -> None:
    if not config.enabled:
        raise AssistantError("V2_DISABLED", "El chat experimental está desactivado.", 503)


async def exception_handler(request: Request, exc: AssistantError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message})


@router.get("/providers")
async def providers(user_id: Admin) -> Capabilities:
    return capabilities()


@router.get("/{draft_id}/history")
async def get_history(draft_id: DraftId, user_id: Admin) -> History:
    require_enabled()
    return await history.read_history(user_id, draft_id)


@router.delete("/{draft_id}/history")
async def delete_history(draft_id: DraftId, user_id: Admin) -> dict[str, bool]:
    require_enabled()
    await history.clear(user_id, draft_id)
    return {"deleted": True}


@router.get("/{draft_id}/revision")
async def get_revision(
    draft_id: DraftId, user_id: Admin, participation: Literal["mixto", "historico"] = "mixto"
) -> Revision:
    require_enabled()
    return await service.revision(draft_id, participation)


@router.post("/{draft_id}/ask/stream")
async def ask_stream(draft_id: DraftId, payload: AskRequest, user_id: Admin) -> StreamingResponse:
    validate_provider(payload.provider, payload.model)
    return StreamingResponse(
        events(lambda progress: service.ask(draft_id, user_id, payload, progress)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
