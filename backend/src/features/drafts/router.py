from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.drafts.schemas import (
    AddPickRequest,
    AddPickResponse,
    CreateDraftRequest,
    CreateDraftResponse,
    DeletePickResponse,
    DraftDetailResponse,
    DraftListResponse,
    PlayerSearchResponse,
    UpdateDraftOrderRequest,
)
from src.features.drafts.service import DraftService
from src.shared.dependencies import get_db, get_draft_manager

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
    _user: dict = Depends(get_draft_manager),
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
    _user: dict = Depends(get_draft_manager),
) -> CreateDraftResponse:
    return await service.create_draft(season_id, body.phase, body.draft_type)


@router.post("/{draft_id}/picks", response_model=AddPickResponse)
async def add_pick(
    draft_id: int,
    body: AddPickRequest,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(get_draft_manager),
) -> AddPickResponse:
    return await service.add_pick(draft_id, body.participant_id, body.player_id)


@router.delete("/{draft_id}/picks/{pick_number}", response_model=DeletePickResponse)
async def delete_pick(
    draft_id: int,
    pick_number: int,
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(get_draft_manager),
) -> DeletePickResponse:
    return await service.delete_pick(draft_id, pick_number)


@router.get("/{draft_id}/players/search", response_model=PlayerSearchResponse)
async def search_players_for_draft(
    draft_id: int,
    q: str = Query(default=""),
    position: str | None = Query(default=None),
    service: DraftService = Depends(_get_service),
    _user: dict = Depends(get_draft_manager),
) -> PlayerSearchResponse:
    return await service.search_players(draft_id, q, position)
