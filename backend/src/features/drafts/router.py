from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthenticationError
from src.features.auth.service import decode_token
from src.features.drafts.schemas import (
    AddPickRequest,
    AddPickResponse,
    CreateDraftRequest,
    CreateDraftResponse,
    DeletePickResponse,
    DraftDetailResponse,
    DraftListResponse,
    DraftPlayerStatsResponse,
    DraftTeamOption,
    PlayerSearchResponse,
    ReorderPicksRequest,
    ReorderPicksResponse,
    UpdateDraftOrderRequest,
)
from src.features.drafts.service import DraftService
from src.features.drafts.websocket import draft_ws_manager
from src.features.drafts.wishlist_schemas import (
    AdminWishlistResponse,
    WishlistResponse,
    WishlistToggleRequest,
    WishlistUpsertRequest,
)
from src.shared.dependencies import (
    get_current_admin,
    get_current_user,
    get_db,
    require_draft_writable,
    require_perm,
    require_season_writable,
)
from src.shared.permissions import Perm

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _get_service(db: AsyncSession = Depends(get_db)) -> DraftService:
    return DraftService(db)


# -------------------------------------------------------------------
# Read endpoints (public — any logged-in user can view drafts)
# -------------------------------------------------------------------


@router.get("/{season_id}", response_model=DraftListResponse)
async def list_drafts(
    season_id: int,
    service: DraftService = Depends(_get_service),
) -> DraftListResponse:
    return await service.list_drafts(season_id)


@router.get("/{draft_id}/teams", response_model=list[DraftTeamOption])
async def list_draft_teams(
    draft_id: int,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(get_current_user),
) -> list[DraftTeamOption]:
    """List the teams of the draft's season — used by the search filter.

    Declared before ``/{season_id}/{phase}`` because FastAPI matches by
    declaration order and that route would otherwise swallow
    ``/drafts/{id}/teams`` (treating "teams" as the phase).
    """
    return await service.list_teams(draft_id)


# -------------------------------------------------------------------
# Wishlist (auto-pick) — declared before /{season_id}/{phase} so the
# 'wishlist' segment is not treated as a phase name.
# -------------------------------------------------------------------


@router.get("/{draft_id}/wishlist", response_model=WishlistResponse)
async def get_my_wishlist(
    draft_id: int,
    service: DraftService = Depends(_get_service),
    user: dict = Depends(get_current_user),
) -> WishlistResponse:
    """Return the caller's auto-pick wishlist for the draft.

    Each player carries ``is_already_picked`` so the UI can grey out
    those that another participant already drafted.
    """
    return await service.get_my_wishlist(draft_id, user)


@router.put("/{draft_id}/wishlist", response_model=WishlistResponse)
async def upsert_my_wishlist(
    draft_id: int,
    body: WishlistUpsertRequest,
    service: DraftService = Depends(_get_service),
    user: dict = Depends(get_current_user),
    _writable: dict = Depends(require_draft_writable),
) -> WishlistResponse:
    """Replace the caller's wishlist with the supplied ordered list."""
    return await service.upsert_my_wishlist(draft_id, user, body)


@router.post("/{draft_id}/wishlist/toggle", response_model=WishlistResponse)
async def toggle_my_wishlist(
    draft_id: int,
    body: WishlistToggleRequest,
    service: DraftService = Depends(_get_service),
    user: dict = Depends(get_current_user),
    _writable: dict = Depends(require_draft_writable),
) -> WishlistResponse:
    """Enable or disable auto-pick for the caller without touching the list."""
    return await service.toggle_my_wishlist(draft_id, user, body.enabled)


@router.get("/admin/{draft_id}/wishlists", response_model=list[AdminWishlistResponse])
async def list_all_wishlists_admin(
    draft_id: int,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.DRAFT)),
) -> list[AdminWishlistResponse]:
    """Admin view: read all wishlists for a draft (audit)."""
    return await service.get_all_wishlists_admin(draft_id)


@router.post("/admin/{draft_id}/pause")
async def pause_draft(
    draft_id: int,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.DRAFT)),
) -> dict:
    """Pause the draft: new picks (manual or auto) are blocked."""
    draft = await service.set_draft_status(draft_id, "pause")
    return {"id": draft.id, "status": draft.status}


@router.post("/admin/{draft_id}/resume")
async def resume_draft(
    draft_id: int,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.DRAFT)),
) -> dict:
    """Resume a paused draft."""
    draft = await service.set_draft_status(draft_id, "resume")
    return {"id": draft.id, "status": draft.status}


@router.get("/{season_id}/{phase}", response_model=DraftDetailResponse)
async def get_draft_detail(
    season_id: int,
    phase: str,
    service: DraftService = Depends(_get_service),
) -> DraftDetailResponse:
    return await service.get_draft_detail(season_id, phase)


# -------------------------------------------------------------------
# Write endpoints (draft manager or admin)
# -------------------------------------------------------------------


@router.put("/{season_id}/participants/order")
async def update_draft_order(
    season_id: int,
    body: UpdateDraftOrderRequest,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.DRAFT)),
    _writable: dict = Depends(require_season_writable),
) -> dict:
    await service.update_draft_order(
        season_id, [(o.participant_id, o.draft_order) for o in body.orders]
    )
    return {"ok": True}


@router.post("/{season_id}", response_model=CreateDraftResponse)
async def create_draft(
    season_id: int,
    body: CreateDraftRequest,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.DRAFT)),
    _writable: dict = Depends(require_season_writable),
) -> CreateDraftResponse:
    return await service.create_draft(season_id, body.phase, body.draft_type)


@router.post("/{draft_id}/picks", response_model=AddPickResponse)
async def add_pick(
    draft_id: int,
    body: AddPickRequest,
    service: DraftService = Depends(_get_service),
    user: dict = Depends(get_current_user),
    _writable: dict = Depends(require_draft_writable),
) -> AddPickResponse:
    """Make a draft pick.

    Authorization is enforced in the service: admins / Perm.DRAFT holders
    can pick for any participant; a regular user may only pick for
    themselves AND only when it's actually their turn.
    """
    return await service.add_pick(draft_id, body.player_id, user, body.participant_id)


@router.put("/{draft_id}/picks/reorder", response_model=ReorderPicksResponse)
async def reorder_picks(
    draft_id: int,
    body: ReorderPicksRequest,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.DRAFT)),
    _writable: dict = Depends(require_draft_writable),
) -> ReorderPicksResponse:
    return await service.reorder_picks(draft_id, body.pick_ids)


@router.delete("/{draft_id}/picks/{pick_number}", response_model=DeletePickResponse)
async def delete_pick(
    draft_id: int,
    pick_number: int,
    service: DraftService = Depends(_get_service),
    user: dict = Depends(get_current_user),
    _writable: dict = Depends(require_draft_writable),
) -> DeletePickResponse:
    """Delete a draft pick.

    Authorization is enforced inside the service: admins / DRAFT permission
    holders can delete any pick; ordinary participants can only delete their
    own LAST pick (no one else may have picked after them).
    """
    return await service.delete_pick(draft_id, pick_number, user)


@router.get("/{draft_id}/players/stats", response_model=DraftPlayerStatsResponse)
async def get_draft_player_stats(
    draft_id: int,
    _admin: dict = Depends(get_current_admin),
    service: DraftService = Depends(_get_service),
) -> DraftPlayerStatsResponse:
    return await service.get_player_stats_for_draft(draft_id)


@router.get("/{draft_id}/players/search", response_model=PlayerSearchResponse)
async def search_players_for_draft(
    draft_id: int,
    q: str = Query(default=""),
    position: str | None = Query(default=None),
    team_id: int | None = Query(default=None),
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(get_current_user),
) -> PlayerSearchResponse:
    """Browse the draft's available player pool.

    Open to any authenticated user — a participant needs to see the list
    when their turn comes. The actual pick (POST /picks) is still gated
    by Perm.DRAFT plus the turn check, and the spectators-only WS already
    requires a token.
    """
    return await service.search_players(draft_id, q, position, team_id)


@router.websocket("/ws/{draft_id}")
async def draft_websocket(
    websocket: WebSocket,
    draft_id: int,
    token: str = "",
) -> None:
    """WebSocket endpoint for live draft updates."""
    # Authenticate via query param
    try:
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return
        decode_token(token)
    except AuthenticationError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await draft_ws_manager.connect(draft_id, websocket)
    try:
        while True:
            # Keep connection alive; we don't expect client messages
            # but we need to listen to detect disconnection
            await websocket.receive_text()
    except WebSocketDisconnect:
        await draft_ws_manager.disconnect(draft_id, websocket)
    except Exception:
        await draft_ws_manager.disconnect(draft_id, websocket)
