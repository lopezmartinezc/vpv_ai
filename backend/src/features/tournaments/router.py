from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.tournaments.schemas import (
    BracketResponse,
    GroupsResponse,
    PlayerOption,
    PredictionRequest,
    PredictionResponse,
    PredictionsListResponse,
    PredictionsStatusResponse,
    RecalculateResponse,
    TeamGroupBatchUpdate,
    TeamOption,
)
from src.features.tournaments.service import TournamentService
from src.shared.dependencies import (
    get_current_user,
    get_db,
    require_perm,
    require_season_writable,
)
from src.shared.permissions import Perm

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


@router.get("/{season_id}/predictions/status", response_model=PredictionsStatusResponse)
async def get_predictions_status(
    season_id: int,
    service: TournamentService = Depends(_get_service),
) -> PredictionsStatusResponse:
    """Public: whether predictions are still open and the deadline."""
    return await service.get_predictions_status(season_id)


@router.get("/{season_id}/predictions/me", response_model=PredictionResponse | None)
async def get_my_prediction(
    season_id: int,
    user: dict = Depends(get_current_user),
    service: TournamentService = Depends(_get_service),
) -> PredictionResponse | None:
    return await service.get_my_prediction(season_id, int(user["sub"]))


@router.put("/{season_id}/predictions/me", response_model=PredictionResponse)
async def upsert_my_prediction(
    season_id: int,
    body: PredictionRequest,
    user: dict = Depends(get_current_user),
    service: TournamentService = Depends(_get_service),
) -> PredictionResponse:
    return await service.upsert_my_prediction(season_id, int(user["sub"]), body)


@router.get("/{season_id}/predictions", response_model=PredictionsListResponse)
async def list_predictions(
    season_id: int,
    _user: dict = Depends(get_current_user),
    service: TournamentService = Depends(_get_service),
) -> PredictionsListResponse:
    return await service.list_predictions(season_id)


@router.get("/{season_id}/teams", response_model=list[TeamOption])
async def list_teams(
    season_id: int,
    service: TournamentService = Depends(_get_service),
) -> list[TeamOption]:
    """Team options for predictions/admin dropdowns."""
    return await service.list_teams(season_id)


@router.get("/{season_id}/players", response_model=list[PlayerOption])
async def list_players(
    season_id: int,
    service: TournamentService = Depends(_get_service),
) -> list[PlayerOption]:
    """Player options for predictions dropdowns."""
    return await service.list_players(season_id)


@router.put(
    "/admin/{season_id}/teams/groups",
    response_model=list[TeamOption],
)
async def assign_team_groups(
    season_id: int,
    body: TeamGroupBatchUpdate,
    service: TournamentService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.PLAYERS, Perm.PARTICIPANTS)),
    _writable: dict = Depends(require_season_writable),
) -> list[TeamOption]:
    """Batch-update teams' tournament group assignments."""
    return await service.assign_team_groups(season_id, body)


@router.post(
    "/admin/{season_id}/predictions/recalculate",
    response_model=RecalculateResponse,
)
async def recalculate_predictions(
    season_id: int,
    service: TournamentService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.PARTICIPANTS, Perm.STATS)),
    _writable: dict = Depends(require_season_writable),
) -> RecalculateResponse:
    """Recalculate bonus_points for all predictions against current results."""
    return await service.recalculate_predictions(season_id)
