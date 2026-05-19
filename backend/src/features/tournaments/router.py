from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.tournaments.schemas import BracketResponse, GroupsResponse
from src.features.tournaments.service import TournamentService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


def _get_service(db: AsyncSession = Depends(get_db)) -> TournamentService:
    return TournamentService(db)


@router.get("/{season_id}/groups", response_model=GroupsResponse)
async def get_groups(
    season_id: int,
    service: TournamentService = Depends(_get_service),
) -> GroupsResponse:
    return await service.get_groups(season_id)


@router.get("/{season_id}/bracket", response_model=BracketResponse)
async def get_bracket(
    season_id: int,
    service: TournamentService = Depends(_get_service),
) -> BracketResponse:
    return await service.get_bracket(season_id)
