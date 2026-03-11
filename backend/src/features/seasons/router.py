from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.seasons.schemas import (
    PaymentsBatchUpdate,
    ScoringRuleResponse,
    ScoringRulesBatchUpdate,
    SeasonDetail,
    SeasonParticipantResponse,
    SeasonPaymentResponse,
    SeasonSummary,
    SeasonUpdateRequest,
    ValidFormationResponse,
)
from src.features.seasons.service import SeasonService
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/seasons", tags=["seasons"])


def _get_service(db: AsyncSession = Depends(get_db)) -> SeasonService:
    return SeasonService(db)


@router.get("", response_model=list[SeasonSummary])
async def list_seasons(
    service: SeasonService = Depends(_get_service),
) -> list[SeasonSummary]:
    seasons = await service.list_seasons()
    return [SeasonSummary.model_validate(s) for s in seasons]


@router.get("/current", response_model=SeasonDetail)
async def get_current_season(
    service: SeasonService = Depends(_get_service),
) -> SeasonDetail:
    season = await service.get_current_season()
    return SeasonDetail.model_validate(season)


@router.get("/formations", response_model=list[ValidFormationResponse])
async def get_valid_formations(
    service: SeasonService = Depends(_get_service),
) -> list[ValidFormationResponse]:
    formations = await service.get_valid_formations()
    return [ValidFormationResponse.model_validate(f) for f in formations]


@router.get(
    "/{season_id}/valid-formations",
    response_model=list[ValidFormationResponse],
)
async def get_valid_formations_by_season(
    season_id: int,
    service: SeasonService = Depends(_get_service),
) -> list[ValidFormationResponse]:
    """Alias: formations are global but frontend passes season_id."""
    formations = await service.get_valid_formations()
    return [ValidFormationResponse.model_validate(f) for f in formations]


@router.get("/{season_id}", response_model=SeasonDetail)
async def get_season(
    season_id: int,
    service: SeasonService = Depends(_get_service),
) -> SeasonDetail:
    season = await service.get_season(season_id)
    return SeasonDetail.model_validate(season)


@router.get("/{season_id}/scoring-rules", response_model=list[ScoringRuleResponse])
async def get_scoring_rules(
    season_id: int,
    service: SeasonService = Depends(_get_service),
) -> list[ScoringRuleResponse]:
    rules = await service.get_scoring_rules(season_id)
    return [ScoringRuleResponse.model_validate(r) for r in rules]


@router.get("/{season_id}/payments", response_model=list[SeasonPaymentResponse])
async def get_season_payments(
    season_id: int,
    service: SeasonService = Depends(_get_service),
) -> list[SeasonPaymentResponse]:
    payments = await service.get_payments(season_id)
    return [SeasonPaymentResponse.model_validate(p) for p in payments]


@router.get("/{season_id}/participants", response_model=list[SeasonParticipantResponse])
async def get_season_participants(
    season_id: int,
    service: SeasonService = Depends(_get_service),
) -> list[SeasonParticipantResponse]:
    participants = await service.get_participants(season_id)
    return [SeasonParticipantResponse.model_validate(p) for p in participants]


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.put("/admin/{season_id}", response_model=SeasonDetail)
async def update_season(
    season_id: int,
    body: SeasonUpdateRequest,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> SeasonDetail:
    return await service.update_season(season_id, **body.model_dump(exclude_none=True))


@router.put(
    "/admin/{season_id}/scoring-rules",
    response_model=list[ScoringRuleResponse],
)
async def update_scoring_rules(
    season_id: int,
    body: ScoringRulesBatchUpdate,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> list[ScoringRuleResponse]:
    updates = [(r.id, r.value) for r in body.rules]
    return await service.update_scoring_rules(season_id, updates)


@router.put(
    "/admin/{season_id}/payments",
    response_model=list[SeasonPaymentResponse],
)
async def update_payments(
    season_id: int,
    body: PaymentsBatchUpdate,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> list[SeasonPaymentResponse]:
    updates = [(p.id, p.amount) for p in body.payments]
    return await service.update_payments(season_id, updates)


@router.put(
    "/admin/{season_id}/participants/{participant_id}/toggle-active",
    response_model=SeasonParticipantResponse,
)
async def toggle_participant_active(
    season_id: int,
    participant_id: int,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> SeasonParticipantResponse:
    participant = await service.toggle_participant_active(season_id, participant_id)
    return SeasonParticipantResponse.model_validate(participant)
