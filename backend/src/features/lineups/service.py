from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.lineups.repository import LineupRepository
from src.features.lineups.schemas import (
    LineupPlayerResponse,
    LineupPlayerSlot,
    LineupSubmitRequest,
    LineupSubmitResponse,
)

logger = logging.getLogger(__name__)


class LineupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LineupRepository(session)

    async def submit_lineup(
        self,
        user_id: int,
        season_id: int,
        matchday_number: int,
        data: LineupSubmitRequest,
    ) -> LineupSubmitResponse:
        """Submit or update a lineup for the current user."""

        # 1. Resolve participant
        participant = await self.repo.get_participant_for_user(season_id, user_id)
        if participant is None:
            raise NotFoundError("Participante", f"user={user_id}, season={season_id}")

        # 2. Get matchday + validate deadline
        matchday = await self.repo.get_matchday(season_id, matchday_number)
        if matchday is None:
            raise NotFoundError("Jornada", matchday_number)

        await self._validate_deadline(matchday, season_id)

        # 3. Validate formation
        vf = await self.repo.get_valid_formation(data.formation)
        if vf is None:
            raise BusinessRuleError(f"Formacion invalida: {data.formation}")

        # 4. Validate positions match formation
        self._validate_positions(data.players, vf)

        # 5. Validate player ownership
        await self._validate_ownership(participant.id, data.players)

        # 6. Validate no duplicate players
        self._validate_no_duplicates(data.players)

        # 7. Upsert lineup
        players_dicts = [
            {"player_id": p.player_id, "position_slot": p.position_slot}
            for p in data.players
        ]
        lineup = await self.repo.upsert_lineup(
            participant_id=participant.id,
            matchday_id=matchday.id,
            formation=data.formation,
            players=players_dicts,
        )

        logger.info(
            "Lineup submitted: lineup_id=%d participant=%d matchday=%d",
            lineup.id, participant.id, matchday.id,
        )

        # 8. Send to Telegram (non-blocking, errors don't fail the submission)
        await self._notify_telegram(lineup.id)

        # Build response
        player_rows = await self.repo.get_lineup_players_response(lineup.id)
        return LineupSubmitResponse(
            lineup_id=lineup.id,
            formation=lineup.formation,
            confirmed=lineup.confirmed,
            confirmed_at=lineup.confirmed_at,
            telegram_sent=lineup.telegram_sent,
            players=[LineupPlayerResponse(**r) for r in player_rows],
        )

    async def apply_deadline_lineups(
        self, season_id: int, matchday_number: int
    ) -> dict[str, int]:
        """Copy previous lineup for participants who haven't submitted one."""
        matchday = await self.repo.get_matchday(season_id, matchday_number)
        if matchday is None:
            raise NotFoundError("Jornada", matchday_number)

        missing = await self.repo.get_participants_without_lineup(
            season_id, matchday.id
        )

        copied = 0
        errors = 0

        for participant in missing:
            try:
                prev = await self.repo.get_previous_lineup(
                    participant.id, season_id, matchday_number
                )
                if prev is None:
                    logger.warning(
                        "No previous lineup for participant=%d matchday=%d",
                        participant.id, matchday_number,
                    )
                    continue

                new_lineup = await self.repo.copy_previous_lineup(
                    from_lineup_id=prev.id,
                    from_formation=prev.formation,
                    participant_id=participant.id,
                    to_matchday_id=matchday.id,
                )
                copied += 1

                # Send to Telegram
                await self._notify_telegram(new_lineup.id)

            except Exception:
                logger.exception(
                    "Error copying lineup for participant=%d", participant.id
                )
                errors += 1

        logger.info(
            "Deadline lineups: copied=%d errors=%d missing_total=%d",
            copied, errors, len(missing),
        )
        return {"copied": copied, "errors": errors, "total_missing": len(missing)}

    async def _validate_deadline(
        self, matchday: object, season_id: int
    ) -> None:
        """Check that the deadline hasn't passed."""
        now = datetime.now(timezone.utc)

        # Use pre-computed deadline_at if available
        deadline = getattr(matchday, "deadline_at", None)

        if deadline is None:
            # Compute from first_match_at - lineup_deadline_min
            first_match = getattr(matchday, "first_match_at", None)
            if first_match is None:
                return  # No deadline info, allow submission

            season = await self.repo.get_season(season_id)
            if season is None:
                return
            deadline = first_match - timedelta(minutes=season.lineup_deadline_min)

        # Make deadline timezone-aware if needed
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        if now >= deadline:
            raise BusinessRuleError(
                "El plazo para enviar la alineacion ha finalizado"
            )

    def _validate_positions(
        self, players: list[LineupPlayerSlot], vf: object
    ) -> None:
        """Validate that position counts match the formation."""
        counts = {"POR": 0, "DEF": 0, "MED": 0, "DEL": 0}
        for p in players:
            counts[p.position_slot] += 1

        expected = {
            "POR": 1,
            "DEF": vf.defenders,  # type: ignore[attr-defined]
            "MED": vf.midfielders,  # type: ignore[attr-defined]
            "DEL": vf.forwards,  # type: ignore[attr-defined]
        }
        if counts != expected:
            raise BusinessRuleError(
                f"Posiciones no coinciden con formacion {vf.formation}: "  # type: ignore[attr-defined]
                f"esperado {expected}, recibido {counts}"
            )

    async def _validate_ownership(
        self, participant_id: int, players: list[LineupPlayerSlot]
    ) -> None:
        """Validate all players belong to the participant's squad."""
        owned = await self.repo.get_participant_player_ids(participant_id)
        submitted = {p.player_id for p in players}
        not_owned = submitted - owned
        if not_owned:
            raise BusinessRuleError(
                f"Jugadores no pertenecen a tu plantilla: {not_owned}"
            )

    def _validate_no_duplicates(self, players: list[LineupPlayerSlot]) -> None:
        ids = [p.player_id for p in players]
        if len(ids) != len(set(ids)):
            raise BusinessRuleError("No se puede repetir jugador en la alineacion")

    async def _notify_telegram(self, lineup_id: int) -> None:
        """Send lineup image to Telegram group. Errors are logged, not raised."""
        try:
            from src.features.telegram.config import telegram_settings

            if not telegram_settings.telegram_enabled:
                return

            from src.features.telegram.service import TelegramNotifier

            notifier = TelegramNotifier(self.session)
            await notifier.send_lineup_image(lineup_id)
        except Exception:
            logger.exception("Failed to send Telegram notification for lineup=%d", lineup_id)
