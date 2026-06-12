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

    async def list_active_seasons(self) -> list[Season]:
        """List all seasons with status='active' (both league and tournament)."""
        return await self.repo.list_active()

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

    async def add_participant(
        self,
        season_id: int,
        user_id: int,
    ) -> ParticipantRow:
        """Add an existing user as a participant of a season.

        Idempotent-friendly: raises if the user is already participating.
        """
        from sqlalchemy import select

        from src.shared.models.participant import SeasonParticipant
        from src.shared.models.user import User

        await self.get_season(season_id)

        # Verify user exists
        user = await self.repo.session.get(User, user_id)
        if user is None:
            raise NotFoundError("User", user_id)

        # Reject duplicates
        stmt = select(SeasonParticipant).where(
            SeasonParticipant.season_id == season_id,
            SeasonParticipant.user_id == user_id,
        )
        existing = await self.repo.session.execute(stmt)
        if existing.scalar_one_or_none() is not None:
            raise BusinessRuleError(
                f"El usuario {user_id} ya es participante de la temporada {season_id}"
            )

        participant = SeasonParticipant(season_id=season_id, user_id=user_id, is_active=True)
        self.repo.session.add(participant)
        await self.repo.session.flush()
        await self.repo.update_total_participants(season_id)
        await self.repo.session.commit()

        return ParticipantRow(
            id=participant.id,
            user_id=user_id,
            display_name=user.display_name,
            draft_order=participant.draft_order,
            is_active=participant.is_active,
            group_name=participant.group_name,
        )

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

        # Block matchday_winter writes for tournament seasons — they have no
        # winter draft. The frontend hides the input but a stray API call
        # could still set a non-null value, which would mislead future code.
        if kwargs.get("matchday_winter") is not None:
            current = await self.get_season(season_id)
            if current.kind == "tournament":
                raise BusinessRuleError(
                    "matchday_winter no aplica a torneos (sin draft de invierno)"
                )

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
        season = await self.get_season(season_id)
        valid_types = {"initial_fee", "weekly_position", "winter_draft_change", "prize"}
        if payment_type not in valid_types:
            raise BusinessRuleError(f"Tipo de pago invalido: {payment_type}")
        # Tournament seasons don't have a winter draft, so the change fee
        # doesn't apply. Block writes from the API as a safety net for the
        # frontend (which already hides the input for tournaments).
        if payment_type == "winter_draft_change" and season.kind == "tournament":
            raise BusinessRuleError(
                "El draft de invierno no aplica a torneos cortos (Mundial, Eurocopa, ...)"
            )
        payment = await self.repo.upsert_payment(
            season_id,
            payment_type,
            position_rank,
            amount,
            description,
        )

        # Apply transactions to participants when updating fees
        from src.features.economy.repository import EconomyRepository

        economy_repo = EconomyRepository(self.repo.session)

        if payment_type == "initial_fee":
            count = await economy_repo.upsert_initial_fees(season_id, amount)
            logger.info(
                "upsert_payment: applied initial_fee=%.2f to %d participants", amount, count
            )
        elif payment_type == "winter_draft_change":
            count = await economy_repo.recalculate_winter_draft_fees(season_id, amount)
            logger.info(
                "upsert_payment: recalculated winter_draft_fee at %.2f/change for %d participants",
                amount,
                count,
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
            kind=request.kind,
            tournament_type=request.tournament_type,
            tournament_config=request.tournament_config,
            telegram_chat_id=request.telegram_chat_id,
            telegram_thread_id=request.telegram_thread_id,
            alerts_telegram_chat_id=request.alerts_telegram_chat_id,
            alerts_telegram_thread_id=request.alerts_telegram_thread_id,
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

        # Always re-lock when finalizing
        updated = await self.repo.update_season(season_id, status="finished", edit_unlocked=False)
        await self.repo.session.commit()
        return SeasonDetail.model_validate(updated)

    async def set_edit_unlocked(self, season_id: int, unlocked: bool) -> SeasonDetail:
        """Toggle the edit_unlocked flag for a finished season.

        Only meaningful when status='finished'. For active/setup seasons
        the flag is irrelevant (writes are always allowed).
        """
        season = await self.get_season(season_id)
        updated = await self.repo.update_season(season_id, edit_unlocked=unlocked)
        await self.repo.session.commit()
        logger.warning(
            "set_edit_unlocked: season_id=%d status=%s edit_unlocked=%s",
            season_id,
            season.status,
            unlocked,
        )
        return SeasonDetail.model_validate(updated)
