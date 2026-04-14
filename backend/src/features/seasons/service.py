from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.scraping.aggregation import ScoreAggregator
from src.features.seasons.repository import ParticipantRow, SeasonRepository
from src.features.seasons.schemas import (
    ScoringRuleResponse,
    SeasonDetail,
    SeasonInitializeRequest,
    SeasonInitializeResponse,
    SeasonPaymentResponse,
)
from src.shared.models.season import ScoringRule, Season, SeasonPayment, ValidFormation

logger = logging.getLogger(__name__)


class SeasonService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = SeasonRepository(session)

    async def list_seasons(self) -> list[Season]:
        return await self.repo.list_all(order_by=Season.id.desc())

    async def get_season(self, season_id: int) -> Season:
        season = await self.repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)
        return season

    async def get_current_season(self) -> Season:
        season = await self.repo.get_current()
        if season is None:
            raise NotFoundError("Season", "current")
        return season

    async def get_scoring_rules(self, season_id: int) -> list[ScoringRule]:
        await self.get_season(season_id)
        return await self.repo.get_scoring_rules(season_id)

    async def get_payments(self, season_id: int) -> list[SeasonPayment]:
        await self.get_season(season_id)
        return await self.repo.get_payments(season_id)

    async def get_valid_formations(self) -> list[ValidFormation]:
        return await self.repo.get_valid_formations()

    async def get_participants(self, season_id: int) -> list[ParticipantRow]:
        await self.get_season(season_id)
        return await self.repo.get_participants(season_id)

    # --- Admin methods ---

    async def assign_participant_group(
        self,
        season_id: int,
        participant_id: int,
        group_name: str | None,
    ) -> ParticipantRow:
        await self.get_season(season_id)
        result = await self.repo.update_participant_group(participant_id, group_name)
        if result is None:
            raise NotFoundError("SeasonParticipant", participant_id)
        await self.repo.session.commit()
        return result

    async def toggle_participant_active(
        self,
        season_id: int,
        participant_id: int,
    ) -> ParticipantRow:
        await self.get_season(season_id)
        result = await self.repo.toggle_participant_active(participant_id)
        if result is None:
            raise NotFoundError("SeasonParticipant", participant_id)
        await self.repo.session.commit()
        return result

    async def update_season(
        self,
        season_id: int,
        **kwargs: object,
    ) -> SeasonDetail:
        valid_statuses = {"setup", "active", "finished"}
        status = kwargs.get("status")
        if status and status not in valid_statuses:
            raise BusinessRuleError(f"Estado invalido: {status}")

        season = await self.repo.update_season(season_id, **kwargs)
        if season is None:
            raise NotFoundError("Season", season_id)

        # Always sync matchday counts — idempotent, ensures consistency
        changed_ids = await self.repo.sync_matchday_counts(
            season_id,
            season.matchday_start,
            matchday_end=season.matchday_end,
        )
        await self.repo.session.commit()

        # Re-aggregate scores for matchdays whose counts flag flipped
        if changed_ids:
            aggregator = ScoreAggregator(self.repo.session)
            for md_id in changed_ids:
                await aggregator.aggregate_matchday(md_id)
            await self.repo.session.commit()

        return SeasonDetail.model_validate(season)

    async def update_payments(
        self,
        season_id: int,
        updates: list[tuple[int, Decimal]],
    ) -> list[SeasonPaymentResponse]:
        await self.get_season(season_id)
        for payment_id, amount in updates:
            result = await self.repo.update_payment(payment_id, amount)
            if result is None:
                raise NotFoundError("SeasonPayment", payment_id)
        await self.repo.session.commit()
        payments = await self.repo.get_payments(season_id)
        return [SeasonPaymentResponse.model_validate(p) for p in payments]

    async def upsert_payment(
        self,
        season_id: int,
        payment_type: str,
        position_rank: int | None,
        amount: Decimal,
        description: str | None,
    ) -> SeasonPaymentResponse:
        await self.get_season(season_id)
        valid_types = {"initial_fee", "weekly_position", "winter_draft_change", "prize"}
        if payment_type not in valid_types:
            raise BusinessRuleError(f"Tipo de pago invalido: {payment_type}")
        payment = await self.repo.upsert_payment(
            season_id,
            payment_type,
            position_rank,
            amount,
            description,
        )
        await self.repo.session.commit()
        return SeasonPaymentResponse.model_validate(payment)

    async def update_scoring_rules(
        self,
        season_id: int,
        updates: list[tuple[int, Decimal]],
    ) -> list[ScoringRuleResponse]:
        await self.get_season(season_id)
        for rule_id, value in updates:
            result = await self.repo.update_scoring_rule(rule_id, value)
            if result is None:
                raise NotFoundError("ScoringRule", rule_id)
        await self.repo.session.commit()
        rules = await self.repo.get_scoring_rules(season_id)
        return [ScoringRuleResponse.model_validate(r) for r in rules]

    # --- Season lifecycle methods ---

    async def initialize_season(
        self,
        request: SeasonInitializeRequest,
    ) -> SeasonInitializeResponse:
        """Create a new season with all config copied from source."""
        # Validate unique name
        if await self.repo.season_name_exists(request.name):
            raise BusinessRuleError(f"Ya existe una temporada con el nombre '{request.name}'")

        # Validate source season if specified
        if request.copy_from_season_id is not None:
            source = await self.repo.get_by_id(request.copy_from_season_id)
            if source is None:
                raise NotFoundError("Season", request.copy_from_season_id)

        # 1. Create season
        season = await self.repo.create_season(
            name=request.name,
            scraping_slug=request.scraping_slug,
            matchday_start=request.matchday_start,
            matchday_end=request.matchday_end,
            draft_pool_size=request.draft_pool_size,
            lineup_deadline_min=request.lineup_deadline_min,
        )

        # 2. Copy scoring rules and payments from source
        scoring_rules_copied = 0
        payments_copied = 0
        if request.copy_from_season_id is not None:
            scoring_rules_copied = await self.repo.copy_scoring_rules(
                request.copy_from_season_id, season.id
            )
            payments_copied = await self.repo.copy_payments(request.copy_from_season_id, season.id)

        # 3. Create participants
        participants_created = 0
        if request.participant_user_ids is not None:
            participants_created = await self.repo.create_participants_from_users(
                season.id, request.participant_user_ids
            )
        elif request.copy_from_season_id is not None:
            participants_created = await self.repo.copy_participants(
                request.copy_from_season_id, season.id
            )

        # 4. Update total_participants
        await self.repo.update_total_participants(season.id)

        # 5. Create matchdays
        matchdays_created = await self.repo.create_matchdays(
            season.id, request.matchday_start, request.matchday_end
        )

        await self.repo.session.commit()

        # Refresh season to get updated total_participants
        refreshed = await self.repo.get_by_id(season.id)

        return SeasonInitializeResponse(
            season=SeasonDetail.model_validate(refreshed),
            participants_created=participants_created,
            scoring_rules_copied=scoring_rules_copied,
            payments_copied=payments_copied,
            matchdays_created=matchdays_created,
            scraping_started=False,
        )

    async def download_photos(self, season_id: int) -> dict[str, int]:
        """Download player photos for a season."""
        await self.get_season(season_id)
        from src.features.scraping.photos import PhotoDownloader

        downloader = PhotoDownloader(self.repo.session)
        result = await downloader.download_all(season_id)
        await self.repo.session.commit()
        return result

    async def finalize_season(self, season_id: int) -> SeasonDetail:
        """Mark season as finished after validation."""
        season = await self.get_season(season_id)
        if season.status != "active":
            raise BusinessRuleError("Solo se puede finalizar una temporada con estado 'active'")

        incomplete = await self.repo.get_incomplete_counting_matchdays(season_id)
        if incomplete:
            raise BusinessRuleError(f"No se puede finalizar: jornadas sin stats_ok: {incomplete}")

        updated = await self.repo.update_season(season_id, status="finished")
        await self.repo.session.commit()
        return SeasonDetail.model_validate(updated)
