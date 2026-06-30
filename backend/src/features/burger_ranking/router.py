"""Public router for the Burger + Bench rankings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.burger_ranking.schemas import (
    BenchRankingResponse,
    BurgerRankingResponse,
    RankingsResponse,
)
from src.features.burger_ranking.service import (
    BenchRankingService,
    BurgerRankingService,
)
from src.features.burger_ranking.survivors import SurvivorsService
from src.shared.dependencies import get_db

router = APIRouter(prefix="/burger-ranking", tags=["rankings"])


def _get_burger(session: AsyncSession = Depends(get_db)) -> BurgerRankingService:
    return BurgerRankingService(session)


def _get_bench(session: AsyncSession = Depends(get_db)) -> BenchRankingService:
    return BenchRankingService(session)


def _get_survivors(session: AsyncSession = Depends(get_db)) -> SurvivorsService:
    return SurvivorsService(session)


@router.get("/{season_id}", response_model=BurgerRankingResponse)
async def get_burger_ranking(
    season_id: int,
    service: BurgerRankingService = Depends(_get_burger),
) -> BurgerRankingResponse:
    return await service.get_ranking(season_id)


# New combined router for the /ranking page.
rankings_router = APIRouter(prefix="/rankings", tags=["rankings"])


@rankings_router.get("/{season_id}", response_model=RankingsResponse)
async def get_all_rankings(
    season_id: int,
    burger: BurgerRankingService = Depends(_get_burger),
    bench: BenchRankingService = Depends(_get_bench),
    survivors: SurvivorsService = Depends(_get_survivors),
) -> RankingsResponse:
    return RankingsResponse(
        season_id=season_id,
        burger=await burger.get_ranking(season_id),
        bench=await bench.get_ranking(season_id),
        survivors=await survivors.get_ranking(season_id),
    )


@rankings_router.get("/{season_id}/bench", response_model=BenchRankingResponse)
async def get_bench_ranking(
    season_id: int,
    service: BenchRankingService = Depends(_get_bench),
) -> BenchRankingResponse:
    return await service.get_ranking(season_id)
