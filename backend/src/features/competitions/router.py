from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.competitions.schemas import (
    CompetitionDetail,
    CompetitionListResponse,
    CompetitionMatchupsResponse,
    CompetitionStandingsResponse,
    CreatePlayoffRequest,
    FormatInfo,
    StartKoRequest,
    StartRegularRequest,
)
from src.features.competitions.service import CompetitionService
from src.shared.dependencies import (
    get_current_admin,
    get_db,
)

router = APIRouter(prefix="/competitions", tags=["competitions"])


def _get_service(db: AsyncSession = Depends(get_db)) -> CompetitionService:
    return CompetitionService(db)


# ---------------------------------------------------------------------------
# Format discovery (public — UI populates the format dropdown from here)
# ---------------------------------------------------------------------------


@router.get("/formats", response_model=list[FormatInfo])
async def list_formats(
    service: CompetitionService = Depends(_get_service),
) -> list[FormatInfo]:
    return service.list_formats()


# ---------------------------------------------------------------------------
# Admin lifecycle endpoints (declared before /season/{id} to avoid swallow)
# ---------------------------------------------------------------------------


@router.post("/admin/season/{season_id}", response_model=CompetitionDetail)
async def create_playoff(
    season_id: int,
    body: CreatePlayoffRequest,
    service: CompetitionService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> CompetitionDetail:
    return await service.create_playoff(season_id, body.format_id)


@router.post("/admin/{competition_id}/start-regular")
async def start_regular_phase(
    competition_id: int,
    body: StartRegularRequest,
    service: CompetitionService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> dict[str, int]:
    inserted = await service.start_regular_phase(
        competition_id,
        body.matchday_start,
        body.matchday_end,
        planned_ko_matchday_numbers=body.planned_ko_matchday_numbers,
    )
    return {"matchups_inserted": inserted}


@router.post("/admin/{competition_id}/start-ko")
async def start_ko_phase(
    competition_id: int,
    body: StartKoRequest,
    service: CompetitionService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> dict[str, int]:
    inserted = await service.start_ko_phase(competition_id, body.ko_matchday_numbers)
    return {"matchups_inserted": inserted}


# ---------------------------------------------------------------------------
# Public reads
# ---------------------------------------------------------------------------


@router.get("/season/{season_id}", response_model=CompetitionListResponse)
async def list_competitions(
    season_id: int,
    service: CompetitionService = Depends(_get_service),
) -> CompetitionListResponse:
    return await service.list_competitions_for_season(season_id)


@router.get("/{competition_id}/matchups", response_model=CompetitionMatchupsResponse)
async def get_matchups(
    competition_id: int,
    service: CompetitionService = Depends(_get_service),
) -> CompetitionMatchupsResponse:
    return await service.get_matchups(competition_id)


@router.get("/{competition_id}/standings", response_model=CompetitionStandingsResponse)
async def get_standings(
    competition_id: int,
    service: CompetitionService = Depends(_get_service),
) -> CompetitionStandingsResponse:
    return await service.get_standings(competition_id)
