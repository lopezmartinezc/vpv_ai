"""Public router for the Burger Ranking."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.burger_ranking.schemas import BurgerRankingResponse
from src.features.burger_ranking.service import BurgerRankingService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/burger-ranking", tags=["burger-ranking"])


def _get_service(session: AsyncSession = Depends(get_db)) -> BurgerRankingService:
    return BurgerRankingService(session)


@router.get("/{season_id}", response_model=BurgerRankingResponse)
async def get_burger_ranking(
    season_id: int,
    service: BurgerRankingService = Depends(_get_service),
) -> BurgerRankingResponse:
    return await service.get_ranking(season_id)
