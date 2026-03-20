from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.achievements.schemas import (
    AchievementDefinitionResponse,
    EvaluationResult,
    SeasonAchievementsResponse,
)
from src.features.achievements.service import AchievementService
from src.shared.dependencies import get_db, require_perm
from src.shared.permissions import Perm

router = APIRouter(prefix="/achievements", tags=["achievements"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AchievementService:
    return AchievementService(db)


@router.get(
    "/definitions",
    response_model=list[AchievementDefinitionResponse],
)
async def list_definitions(
    service: AchievementService = Depends(_get_service),
) -> list[AchievementDefinitionResponse]:
    return await service.get_definitions()


@router.get(
    "/{season_id}",
    response_model=SeasonAchievementsResponse,
)
async def get_season_achievements(
    season_id: int,
    service: AchievementService = Depends(_get_service),
    _admin: dict = Depends(require_perm(Perm.ACHIEVEMENTS)),
) -> SeasonAchievementsResponse:
    return await service.get_season_achievements(season_id)


@router.get(
    "/{season_id}/{participant_id}",
    response_model=SeasonAchievementsResponse,
)
async def get_participant_achievements(
    season_id: int,
    participant_id: int,
    service: AchievementService = Depends(_get_service),
    _admin: dict = Depends(require_perm(Perm.ACHIEVEMENTS)),
) -> SeasonAchievementsResponse:
    return await service.get_participant_achievements(season_id, participant_id)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/admin/{season_id}/evaluate/{number}",
    response_model=EvaluationResult,
)
async def evaluate_matchday(
    season_id: int,
    number: int,
    service: AchievementService = Depends(_get_service),
    _admin: dict = Depends(require_perm(Perm.ACHIEVEMENTS)),
) -> EvaluationResult:
    return await service.evaluate_matchday(season_id, number)


@router.post(
    "/admin/{season_id}/evaluate-all",
    response_model=list[EvaluationResult],
)
async def evaluate_all_matchdays(
    season_id: int,
    service: AchievementService = Depends(_get_service),
    _admin: dict = Depends(require_perm(Perm.ACHIEVEMENTS)),
) -> list[EvaluationResult]:
    return await service.evaluate_all_matchdays(season_id)
