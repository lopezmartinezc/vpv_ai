from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.seasons.schemas import (
    AddParticipantRequest,
    EditUnlockRequest,
    GroupAssignRequest,
    PaymentsBatchUpdate,
    PaymentUpsertRequest,
    PhotoDownloadResponse,
    ScoringRuleResponse,
    ScoringRulesBatchUpdate,
    SeasonCleanRequest,
    SeasonDetail,
    SeasonFinalizeResponse,
    SeasonInitializeRequest,
    SeasonInitializeResponse,
    SeasonParticipantResponse,
    SeasonPaymentResponse,
    SeasonScrapeStatusResponse,
    SeasonSummary,
    SeasonUpdateRequest,
    ValidFormationResponse,
)
from src.features.seasons.service import SeasonService
from src.shared.dependencies import (
    get_current_admin,
    get_db,
    require_perm,
    require_season_writable,
)
from src.shared.permissions import Perm

logger = logging.getLogger(__name__)

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


@router.get("/active", response_model=list[SeasonSummary])
async def list_active_seasons(
    service: SeasonService = Depends(_get_service),
) -> list[SeasonSummary]:
    """Return ALL active seasons (Liga + Tournament).

    Used by the frontend competition switcher to know which competitions
    are currently playable.
    """
    seasons = await service.list_active_seasons()
    return [SeasonSummary.model_validate(s) for s in seasons]


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


@router.post("/admin/initialize", response_model=SeasonInitializeResponse)
async def initialize_season(
    body: SeasonInitializeRequest,
    background_tasks: BackgroundTasks,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> SeasonInitializeResponse:
    """Create a new season with config copied from source, then scrape teams in background."""
    result = await service.initialize_season(body)

    # Launch background task for scraping teams/players/calendar
    background_tasks.add_task(_background_import_teams, result.season.id, body.scraping_slug)
    result.scraping_started = True

    return result


@router.get("/admin/{season_id}/scrape-status", response_model=SeasonScrapeStatusResponse)
async def get_scrape_status(
    season_id: int,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> SeasonScrapeStatusResponse:
    """What has been scraped for this season (teams/players/calendar/photos)
    and the result of the last team import."""
    return await service.get_scrape_status(season_id)


@router.post("/admin/{season_id}/reimport", response_model=dict)
async def reimport_teams(
    season_id: int,
    background_tasks: BackgroundTasks,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
    _writable: dict = Depends(require_season_writable),
) -> dict:
    """Re-run the team/player/calendar import for an existing season.

    Idempotent: create_team/create_player skip rows that already exist via
    their unique constraints. Runs in the background; poll scrape-status."""
    season = await service.get_season(season_id)
    slug = season.scraping_slug or ""
    background_tasks.add_task(_background_import_teams, season_id, slug)
    return {"reimport_started": True}


@router.post("/admin/{season_id}/scrape/teams", response_model=dict)
async def scrape_teams_only(
    season_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
    _writable: dict = Depends(require_season_writable),
) -> dict:
    """Scrape only the teams from the homepage (idempotent, synchronous)."""
    from src.features.scraping.service import ScrapingService

    result = await ScrapingService(db).import_teams_only(season_id)
    await db.commit()
    return result


@router.post("/admin/{season_id}/scrape/rosters", response_model=dict)
async def scrape_rosters_only(
    season_id: int,
    background_tasks: BackgroundTasks,
    _admin: dict = Depends(get_current_admin),
    _writable: dict = Depends(require_season_writable),
) -> dict:
    """Re-fetch every team's roster and create missing players (background)."""
    background_tasks.add_task(_background_rosters, season_id)
    return {"rosters_started": True}


@router.post("/admin/{season_id}/clean", response_model=dict)
async def clean_scraped(
    season_id: int,
    body: SeasonCleanRequest,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
    _writable: dict = Depends(require_season_writable),
) -> dict:
    """Delete scraped rows (all / calendar / rosters / teams) so the season
    can be re-imported cleanly. Only allowed on a 'setup' season with no
    game data."""
    return await service.clean_scraped(season_id, body.part)


@router.put("/admin/{season_id}", response_model=SeasonDetail)
async def update_season(
    season_id: int,
    body: SeasonUpdateRequest,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
    _writable: dict = Depends(require_season_writable),
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
    _writable: dict = Depends(require_season_writable),
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
    _writable: dict = Depends(require_season_writable),
) -> list[SeasonPaymentResponse]:
    updates = [(p.id, p.amount) for p in body.payments]
    return await service.update_payments(season_id, updates)


@router.post(
    "/admin/{season_id}/payments",
    response_model=SeasonPaymentResponse,
)
async def upsert_payment(
    season_id: int,
    body: PaymentUpsertRequest,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
    _writable: dict = Depends(require_season_writable),
) -> SeasonPaymentResponse:
    return await service.upsert_payment(
        season_id,
        body.payment_type,
        body.position_rank,
        body.amount,
        body.description,
    )


@router.post(
    "/admin/{season_id}/participants",
    response_model=SeasonParticipantResponse,
)
async def add_participant(
    season_id: int,
    body: AddParticipantRequest,
    service: SeasonService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.PARTICIPANTS)),
    _writable: dict = Depends(require_season_writable),
) -> SeasonParticipantResponse:
    participant = await service.add_participant(season_id, body.user_id)
    return SeasonParticipantResponse.model_validate(participant)


@router.put(
    "/admin/{season_id}/participants/{participant_id}/toggle-active",
    response_model=SeasonParticipantResponse,
)
async def toggle_participant_active(
    season_id: int,
    participant_id: int,
    service: SeasonService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.PARTICIPANTS)),
    _writable: dict = Depends(require_season_writable),
) -> SeasonParticipantResponse:
    participant = await service.toggle_participant_active(season_id, participant_id)
    return SeasonParticipantResponse.model_validate(participant)


@router.put(
    "/admin/{season_id}/participants/{participant_id}/group",
    response_model=SeasonParticipantResponse,
)
async def assign_participant_group(
    season_id: int,
    participant_id: int,
    body: GroupAssignRequest,
    service: SeasonService = Depends(_get_service),
    _user: dict = Depends(require_perm(Perm.PARTICIPANTS)),
    _writable: dict = Depends(require_season_writable),
) -> SeasonParticipantResponse:
    participant = await service.assign_participant_group(
        season_id, participant_id, body.group_name
    )
    return SeasonParticipantResponse.model_validate(participant)


@router.post("/admin/{season_id}/download-photos", response_model=PhotoDownloadResponse)
async def download_photos(
    season_id: int,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
    _writable: dict = Depends(require_season_writable),
) -> PhotoDownloadResponse:
    """Download player photos for a season (may take several minutes)."""
    result = await service.download_photos(season_id)
    return PhotoDownloadResponse(**result)


@router.put("/admin/{season_id}/finalize", response_model=SeasonFinalizeResponse)
async def finalize_season(
    season_id: int,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> SeasonFinalizeResponse:
    """Mark season as finished after validating all matchday stats are complete."""
    season_detail = await service.finalize_season(season_id)
    return SeasonFinalizeResponse(season=season_detail)


@router.put("/admin/{season_id}/edit-unlock", response_model=SeasonDetail)
async def set_edit_unlock(
    season_id: int,
    body: EditUnlockRequest,
    service: SeasonService = Depends(_get_service),
    _admin: dict = Depends(get_current_admin),
) -> SeasonDetail:
    """Toggle edit_unlocked flag for a finished season (admin override)."""
    return await service.set_edit_unlocked(season_id, body.unlocked)


# ---------------------------------------------------------------------------
# Background task for team/player import
# ---------------------------------------------------------------------------


async def _background_rosters(season_id: int) -> None:
    """Re-fetch rosters for a season in a fresh DB session."""
    from src.core.database import AsyncSessionLocal
    from src.features.scraping.service import ScrapingService

    async with AsyncSessionLocal() as session:
        try:
            result = await ScrapingService(session).import_rosters_only(season_id)
            await session.commit()
            logger.info("background_rosters: season_id=%d — %s", season_id, result)
        except Exception:
            await session.rollback()
            logger.exception("background_rosters: season_id=%d failed", season_id)


async def _background_import_teams(season_id: int, scraping_slug: str) -> None:
    """Run team/player/calendar import in a fresh DB session, then persist a
    ``import_setup`` scraping-log row so the admin can see the result."""
    from src.core.database import AsyncSessionLocal
    from src.features.scraping.log_repository import ScrapingLogRepository
    from src.features.scraping.service import ScrapingService

    async with AsyncSessionLocal() as session:
        try:
            scraping_service = ScrapingService(session)
            result = await scraping_service.import_teams_and_players(season_id, scraping_slug)
            await session.commit()
            logger.info(
                "background_import_teams: season_id=%d complete — %s",
                season_id,
                result,
            )
            await ScrapingLogRepository.write_log(
                {
                    "season_id": season_id,
                    "job_type": "import_setup",
                    "status": "ok",
                    "message": (
                        f"{result['teams']} equipos, {result['players']} jugadores, "
                        f"{result['matches']} partidos"
                    ),
                    "detail": result,
                }
            )
        except Exception as exc:
            await session.rollback()
            logger.exception("background_import_teams: season_id=%d failed", season_id)
            await ScrapingLogRepository.write_log(
                {
                    "season_id": season_id,
                    "job_type": "import_setup",
                    "status": "error",
                    "message": f"Import falló: {exc}",
                }
            )
