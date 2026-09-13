from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.matchdays.closing import CloseReport, MatchdayClosing
from src.features.matchdays.schemas import (
    AdminMatchdayResponse,
    AdminMatchResponse,
    CloseReportResponse,
    CloseStepResponse,
    LineupDetailResponse,
    MatchdayDetailResponse,
    MatchdayHighlightsResponse,
    MatchdayListResponse,
    MatchdayStatusResponse,
    MatchdayUpdateRequest,
    MatchUpdateRequest,
)
from src.features.matchdays.service import MatchdayService
from src.shared.dependencies import get_db, require_perm, require_season_writable
from src.shared.permissions import Perm

router = APIRouter(prefix="/matchdays", tags=["matchdays"])


def _get_service(db: AsyncSession = Depends(get_db)) -> MatchdayService:
    return MatchdayService(db)


@router.get("/{season_id}", response_model=MatchdayListResponse)
async def list_matchdays(
    season_id: int,
    stats_ok_only: bool = Query(default=True),
    service: MatchdayService = Depends(_get_service),
) -> MatchdayListResponse:
    return await service.list_matchdays(
        season_id,
        stats_ok_only=stats_ok_only,
    )


@router.get("/{season_id}/{number}", response_model=MatchdayDetailResponse)
async def get_matchday_detail(
    season_id: int,
    number: int,
    service: MatchdayService = Depends(_get_service),
) -> MatchdayDetailResponse:
    return await service.get_matchday_detail(season_id, number)


@router.get(
    "/{season_id}/{number}/highlights",
    response_model=MatchdayHighlightsResponse,
)
async def get_matchday_highlights(
    season_id: int,
    number: int,
    service: MatchdayService = Depends(_get_service),
) -> MatchdayHighlightsResponse:
    return await service.get_matchday_highlights(season_id, number)


@router.get(
    "/{season_id}/{number}/lineup/{participant_id}",
    response_model=LineupDetailResponse,
)
async def get_lineup_detail(
    season_id: int,
    number: int,
    participant_id: int,
    service: MatchdayService = Depends(_get_service),
) -> LineupDetailResponse:
    return await service.get_lineup_detail(season_id, number, participant_id)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.put(
    "/admin/{season_id}/{number}",
    response_model=AdminMatchdayResponse,
)
async def update_matchday(
    season_id: int,
    number: int,
    body: MatchdayUpdateRequest,
    service: MatchdayService = Depends(_get_service),
    _admin: dict = Depends(require_perm(Perm.MATCHDAYS)),
    _writable: dict = Depends(require_season_writable),
) -> AdminMatchdayResponse:
    return await service.update_matchday(
        season_id,
        number,
        **body.model_dump(exclude_none=True),
    )


@router.put(
    "/admin/{season_id}/{number}/match/{match_id}",
    response_model=AdminMatchResponse,
)
async def update_match(
    season_id: int,
    number: int,
    match_id: int,
    body: MatchUpdateRequest,
    service: MatchdayService = Depends(_get_service),
    _admin: dict = Depends(require_perm(Perm.MATCHDAYS)),
    _writable: dict = Depends(require_season_writable),
) -> AdminMatchResponse:
    return await service.update_match(
        match_id,
        **body.model_dump(exclude_none=True),
    )


# ---------------------------------------------------------------------------
# Matchday centre
# ---------------------------------------------------------------------------


def _closing(db: AsyncSession = Depends(get_db)) -> MatchdayClosing:
    return MatchdayClosing(db)


@router.get("/admin/{season_id}/{number}/estado", response_model=MatchdayStatusResponse)
async def get_matchday_state(
    season_id: int,
    number: int,
    closing: MatchdayClosing = Depends(_closing),
    _admin: dict = Depends(require_perm(Perm.MATCHDAYS)),
) -> MatchdayStatusResponse:
    """State of a jornada and what closing it would do — read-only, both parts.

    The preview runs the close with ``dry_run``, so the panel can show the
    consequences of an operation that pays money out before anyone asks for it.
    """
    state = await closing.status(season_id, number)
    if state is None:
        raise NotFoundError("Matchday", number)
    preview = await closing.close(season_id, number, dry_run=True)
    return MatchdayStatusResponse(
        **{k: v for k, v in vars(state).items()},
        can_close=state.can_close,
        preview=_report(preview),
    )


@router.post("/admin/{season_id}/{number}/cerrar", response_model=CloseReportResponse)
async def close_matchday(
    season_id: int,
    number: int,
    closing: MatchdayClosing = Depends(_closing),
    _admin: dict = Depends(require_perm(Perm.MATCHDAYS)),
    _writable: dict = Depends(require_season_writable),
) -> CloseReportResponse:
    """Close a jornada by hand, for when the automatic path is stuck.

    ``require_season_writable`` is what keeps this off historical seasons: a
    finished season refuses unless a super-admin has explicitly unlocked edits,
    and that override is logged.
    """
    return _report(await closing.close(season_id, number, dry_run=False))


def _report(report: CloseReport) -> CloseReportResponse:
    return CloseReportResponse(
        season_id=report.season_id,
        matchday_number=report.matchday_number,
        dry_run=report.dry_run,
        closed=report.closed,
        blockers=report.blockers,
        steps=[
            CloseStepResponse(name=s.name, outcome=s.outcome, detail=s.detail)
            for s in report.steps
        ],
    )
