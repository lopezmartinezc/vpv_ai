from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineups.schemas import (
    AccuracyRankingResponse,
    AccuracyResponse,
    AdminLineupEditResponse,
    AdminMatchdayLineupsResponse,
    AdminSquadResponse,
    DeadlineStatusResponse,
    LineupHistoryResponse,
    LineupSubmitRequest,
    LineupSubmitResponse,
    MyLineupResponse,
)
from src.features.lineups.service import LineupService
from src.shared.dependencies import get_current_user, get_db, require_perm
from src.shared.permissions import Perm

router = APIRouter(prefix="/lineups", tags=["lineups"])


def _get_service(db: AsyncSession = Depends(get_db)) -> LineupService:
    return LineupService(db)


@router.get(
    "/{season_id}/{matchday_number}/me",
    response_model=MyLineupResponse,
)
async def get_my_lineup(
    season_id: int,
    matchday_number: int,
    user: dict = Depends(get_current_user),
    service: LineupService = Depends(_get_service),
) -> MyLineupResponse:
    """Get lineup context for the current user: squad, existing lineup, deadline."""
    return await service.get_my_lineup(
        user_id=int(user["sub"]),
        season_id=season_id,
        matchday_number=matchday_number,
    )


@router.post(
    "/{season_id}/{matchday_number}",
    response_model=LineupSubmitResponse,
)
async def submit_lineup(
    season_id: int,
    matchday_number: int,
    data: LineupSubmitRequest,
    user: dict = Depends(get_current_user),
    service: LineupService = Depends(_get_service),
) -> LineupSubmitResponse:
    """Submit or update lineup for the current matchday."""
    return await service.submit_lineup(
        user_id=int(user["sub"]),
        season_id=season_id,
        matchday_number=matchday_number,
        data=data,
    )


@router.get(
    "/{season_id}/accuracy/ranking",
    response_model=AccuracyRankingResponse,
)
async def get_accuracy_ranking(
    season_id: int,
    matchday: int | None = None,
    service: LineupService = Depends(_get_service),
) -> AccuracyRankingResponse:
    """Accuracy ranking for all participants. Optional ?matchday=N for single matchday detail."""
    return await service.get_accuracy_ranking(season_id, matchday_number=matchday)


@router.get(
    "/{season_id}/accuracy",
    response_model=AccuracyResponse,
)
async def get_lineup_accuracy(
    season_id: int,
    user: dict = Depends(get_current_user),
    service: LineupService = Depends(_get_service),
) -> AccuracyResponse:
    """Calculate lineup accuracy: actual vs optimal XI per matchday."""
    return await service.get_lineup_accuracy(
        user_id=int(user["sub"]),
        season_id=season_id,
    )


@router.get(
    "/{season_id}/history",
    response_model=LineupHistoryResponse,
)
async def get_lineup_history(
    season_id: int,
    user: dict = Depends(get_current_user),
    service: LineupService = Depends(_get_service),
) -> LineupHistoryResponse:
    """Get all lineups for the current user in a season."""
    return await service.get_lineup_history(
        user_id=int(user["sub"]),
        season_id=season_id,
    )


@router.get(
    "/{season_id}/deadline-status",
    response_model=DeadlineStatusResponse,
)
async def get_deadline_status(
    season_id: int,
    user: dict = Depends(get_current_user),
    service: LineupService = Depends(_get_service),
) -> DeadlineStatusResponse:
    """Check if user has lineup and time remaining until deadline."""
    return await service.get_deadline_status(
        user_id=int(user["sub"]),
        season_id=season_id,
    )


@router.post(
    "/admin/{season_id}/{matchday_number}/apply-deadline",
)
async def apply_deadline_lineups(
    season_id: int,
    matchday_number: int,
    _admin: dict = Depends(require_perm(Perm.LINEUPS_ADMIN)),
    service: LineupService = Depends(_get_service),
) -> dict:
    """Copy previous lineup for participants who missed the deadline."""
    return await service.apply_deadline_lineups(season_id, matchday_number)


@router.get(
    "/admin/{season_id}/{matchday_number}/all",
    response_model=AdminMatchdayLineupsResponse,
)
async def get_admin_matchday_lineups(
    season_id: int,
    matchday_number: int,
    _admin: dict = Depends(require_perm(Perm.LINEUPS_ADMIN)),
    service: LineupService = Depends(_get_service),
) -> AdminMatchdayLineupsResponse:
    """Get all participant lineups for a matchday (admin view)."""
    return await service.get_admin_matchday_lineups(season_id, matchday_number)


@router.get(
    "/admin/{season_id}/{matchday_number}/{participant_id}/squad",
    response_model=AdminSquadResponse,
)
async def get_admin_squad(
    season_id: int,
    matchday_number: int,
    participant_id: int,
    _admin: dict = Depends(require_perm(Perm.LINEUPS_ADMIN)),
    service: LineupService = Depends(_get_service),
) -> AdminSquadResponse:
    """Get participant squad with matchday-specific points."""
    return await service.get_admin_squad(season_id, matchday_number, participant_id)


@router.put(
    "/admin/{season_id}/{matchday_number}/{participant_id}",
    response_model=AdminLineupEditResponse,
)
async def admin_edit_lineup(
    season_id: int,
    matchday_number: int,
    participant_id: int,
    data: LineupSubmitRequest,
    _admin: dict = Depends(require_perm(Perm.LINEUPS_ADMIN)),
    service: LineupService = Depends(_get_service),
) -> AdminLineupEditResponse:
    """Admin: edit a participant's lineup and recalculate scores."""
    return await service.admin_edit_lineup(season_id, matchday_number, participant_id, data)
