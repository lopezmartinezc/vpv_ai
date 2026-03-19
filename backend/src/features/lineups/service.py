from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.lineups.repository import LineupRepository
from src.features.lineups.schemas import (
    AccuracyResponse,
    DeadlineStatusResponse,
    FormMatch,
    LineupHistoryEntry,
    LineupHistoryPlayerEntry,
    LineupHistoryResponse,
    LineupPlayerResponse,
    LineupPlayerSlot,
    LineupSubmitRequest,
    LineupSubmitResponse,
    MatchdayAccuracy,
    MissedCall,
    MyLineupResponse,
    PlayerRecentForm,
    SquadPlayerForLineup,
)

logger = logging.getLogger(__name__)


class LineupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LineupRepository(session)

    async def get_my_lineup(
        self,
        user_id: int,
        season_id: int,
        matchday_number: int,
    ) -> MyLineupResponse:
        """Get the current user's lineup context for a matchday."""
        participant = await self.repo.get_participant_for_user(season_id, user_id)
        if participant is None:
            raise NotFoundError("Participante", f"user={user_id}, season={season_id}")

        season = await self.repo.get_season(season_id)
        if season is None:
            raise NotFoundError("Temporada", season_id)

        matchday = await self.repo.get_matchday(season_id, matchday_number)
        if matchday is None:
            raise NotFoundError("Jornada", matchday_number)

        # Get existing lineup (if any)
        current_lineup = None
        lineup = await self.repo.get_lineup(participant.id, matchday.id)
        if lineup is not None:
            player_rows = await self.repo.get_lineup_players_response(lineup.id)
            current_lineup = LineupSubmitResponse(
                lineup_id=lineup.id,
                formation=lineup.formation,
                confirmed=lineup.confirmed,
                confirmed_at=lineup.confirmed_at,
                telegram_sent=lineup.telegram_sent,
                players=[LineupPlayerResponse(**r) for r in player_rows],
            )

        # Get squad players
        squad_rows = await self.repo.get_squad_players(season_id, participant.id)

        # Get recent form for all squad players
        player_ids = [r["player_id"] for r in squad_rows]
        form_data = await self.repo.get_squad_recent_form(season_id, player_ids)

        # Get display_name from the user
        from src.shared.models.user import User

        user_obj = await self.session.get(User, user_id)
        display_name = user_obj.display_name if user_obj else "Unknown"

        squad: list[SquadPlayerForLineup] = []
        for r in squad_rows:
            pid = r["player_id"]
            form = form_data.get(pid)
            recent_form = None
            if form:
                recent_form = PlayerRecentForm(
                    matches=[
                        FormMatch(
                            played=m["played"],
                            result=m["result"],
                            is_home=m["is_home"],
                            points=m["points"],
                        )
                        for m in form["matches"]
                    ],
                    clean_sheets=form["clean_sheets"],
                    goals=form["goals"],
                    assists=form["assists"],
                    penalty_goals=form["penalty_goals"],
                    yellow_cards=form["yellow_cards"],
                )
            squad.append(
                SquadPlayerForLineup(
                    player_id=pid,
                    display_name=r["display_name"],
                    photo_path=r["photo_path"],
                    position=r["position"],
                    team_name=r["team_name"],
                    season_points=r["season_points"],
                    recent_form=recent_form,
                )
            )

        return MyLineupResponse(
            participant_id=participant.id,
            display_name=display_name,
            lineup_deadline_min=season.lineup_deadline_min,
            current_lineup=current_lineup,
            squad=squad,
        )

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
            {"player_id": p.player_id, "position_slot": p.position_slot} for p in data.players
        ]
        lineup = await self.repo.upsert_lineup(
            participant_id=participant.id,
            matchday_id=matchday.id,
            formation=data.formation,
            players=players_dicts,
        )

        logger.info(
            "Lineup submitted: lineup_id=%d participant=%d matchday=%d",
            lineup.id,
            participant.id,
            matchday.id,
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

    async def apply_deadline_lineups(self, season_id: int, matchday_number: int) -> dict[str, int]:
        """Copy previous lineup for participants who haven't submitted one."""
        matchday = await self.repo.get_matchday(season_id, matchday_number)
        if matchday is None:
            raise NotFoundError("Jornada", matchday_number)

        missing = await self.repo.get_participants_without_lineup(season_id, matchday.id)

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
                        participant.id,
                        matchday_number,
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
                logger.exception("Error copying lineup for participant=%d", participant.id)
                errors += 1

        logger.info(
            "Deadline lineups: copied=%d errors=%d missing_total=%d",
            copied,
            errors,
            len(missing),
        )
        return {"copied": copied, "errors": errors, "total_missing": len(missing)}

    async def get_deadline_status(self, user_id: int, season_id: int) -> DeadlineStatusResponse:
        """Check if the current user has a lineup and how much time is left."""
        season = await self.repo.get_season(season_id)
        if season is None:
            raise NotFoundError("Temporada", season_id)

        md_number = season.matchday_current
        if md_number == 0:
            return DeadlineStatusResponse(has_lineup=True, matchday_number=0)

        matchday = await self.repo.get_matchday(season_id, md_number)
        if matchday is None:
            return DeadlineStatusResponse(has_lineup=True, matchday_number=md_number)

        # Compute deadline
        deadline = matchday.deadline_at
        if deadline is None and matchday.first_match_at is not None:
            deadline = matchday.first_match_at - timedelta(minutes=season.lineup_deadline_min)

        if deadline is not None and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)

        # Check if user has lineup
        participant = await self.repo.get_participant_for_user(season_id, user_id)
        has_lineup = False
        if participant is not None:
            lineup = await self.repo.get_lineup(participant.id, matchday.id)
            has_lineup = lineup is not None

        minutes_remaining = None
        if deadline is not None:
            now = datetime.now(UTC)
            diff = (deadline - now).total_seconds() / 60
            minutes_remaining = max(0, int(diff))

        return DeadlineStatusResponse(
            has_lineup=has_lineup,
            deadline_at=deadline,
            minutes_remaining=minutes_remaining,
            matchday_number=md_number,
        )

    async def get_lineup_history(self, user_id: int, season_id: int) -> LineupHistoryResponse:
        """Get all lineups for the current user in a season."""
        participant = await self.repo.get_participant_for_user(season_id, user_id)
        if participant is None:
            raise NotFoundError("Participante", f"user={user_id}, season={season_id}")

        season = await self.repo.get_season(season_id)
        if season is None:
            raise NotFoundError("Temporada", season_id)

        from src.shared.models.user import User

        user_obj = await self.session.get(User, user_id)
        display_name = user_obj.display_name if user_obj else "Unknown"

        rows = await self.repo.get_participant_lineups(participant.id, season_id)

        lineups = [
            LineupHistoryEntry(
                matchday_number=r["matchday_number"],
                formation=r["formation"],
                total_points=r["total_points"],
                confirmed_at=r["confirmed_at"],
                players=[LineupHistoryPlayerEntry(**p) for p in r["players"]],
            )
            for r in rows
        ]

        return LineupHistoryResponse(
            participant_id=participant.id,
            display_name=display_name,
            season_name=season.name,
            lineups=lineups,
        )

    async def get_lineup_accuracy(self, user_id: int, season_id: int) -> AccuracyResponse:
        """Calculate how well the user picked their XI each matchday."""
        participant = await self.repo.get_participant_for_user(season_id, user_id)
        if participant is None:
            raise NotFoundError("Participante", f"user={user_id}, season={season_id}")

        season = await self.repo.get_season(season_id)
        if season is None:
            raise NotFoundError("Temporada", season_id)

        from src.shared.models.user import User

        user_obj = await self.session.get(User, user_id)
        display_name = user_obj.display_name if user_obj else "Unknown"

        raw_data = await self.repo.get_accuracy_data(participant.id, season_id)
        formations = await self.repo.get_valid_formations()

        matchday_accuracies: list[MatchdayAccuracy] = []
        total_missed = 0
        perfect = 0

        for md_data in raw_data:
            squad_stats = md_data["squad_stats"]
            lined_up_ids: set[int] = md_data["lined_up_ids"]
            actual = md_data["actual_points"]
            formation_used = md_data["formation"]

            # Calculate optimal XI
            optimal, optimal_formation, optimal_ids = self._calc_optimal(squad_stats, formations)

            accuracy = round(actual / optimal * 100, 1) if optimal > 0 else 100.0
            if accuracy >= 95:
                perfect += 1
            total_missed += max(0, optimal - actual)

            # Build missed calls: benched players who scored more than a lined-up
            # player in the same position (top 3 biggest diffs)
            missed_calls = self._build_missed_calls(squad_stats, lined_up_ids, optimal_ids)

            matchday_accuracies.append(
                MatchdayAccuracy(
                    matchday_number=md_data["matchday_number"],
                    actual_points=actual,
                    optimal_points=optimal,
                    accuracy_pct=accuracy,
                    formation_used=formation_used,
                    optimal_formation=optimal_formation,
                    missed_calls=missed_calls,
                )
            )

        n = len(matchday_accuracies)
        avg = round(sum(m.accuracy_pct for m in matchday_accuracies) / n, 1) if n else 0

        return AccuracyResponse(
            participant_id=participant.id,
            display_name=display_name,
            season_name=season.name,
            avg_accuracy=avg,
            perfect_weeks=perfect,
            total_missed_points=total_missed,
            matchdays=matchday_accuracies,
        )

    @staticmethod
    def _calc_optimal(squad_stats: list[dict], formations: list) -> tuple[int, str, set[int]]:
        """Try all formations and return (max_points, formation_name, player_ids)."""
        # Group by position, sorted by pts DESC
        by_pos: dict[str, list[dict]] = {"POR": [], "DEF": [], "MED": [], "DEL": []}
        for s in squad_stats:
            pos = s["position"]
            if pos in by_pos:
                by_pos[pos].append(s)
        for pos in by_pos:
            by_pos[pos].sort(key=lambda x: x["pts"], reverse=True)

        best_total = 0
        best_formation = ""
        best_ids: set[int] = set()

        for f in formations:
            picks: list[dict] = []
            picks.extend(by_pos["POR"][:1])
            picks.extend(by_pos["DEF"][: f.defenders])
            picks.extend(by_pos["MED"][: f.midfielders])
            picks.extend(by_pos["DEL"][: f.forwards])

            total = sum(p["pts"] for p in picks)
            if total > best_total:
                best_total = total
                best_formation = f.formation
                best_ids = {p["player_id"] for p in picks}

        return best_total, best_formation, best_ids

    @staticmethod
    def _build_missed_calls(
        squad_stats: list[dict],
        lined_up_ids: set[int],
        optimal_ids: set[int],
    ) -> list[MissedCall]:
        """Find players who should have been lined up but weren't (top 3)."""
        # Players in optimal but NOT in actual lineup
        should_have = {s["player_id"]: s for s in squad_stats if s["player_id"] in optimal_ids}
        actually_lined = {s["player_id"]: s for s in squad_stats if s["player_id"] in lined_up_ids}

        diffs: list[MissedCall] = []
        for pid, benched in should_have.items():
            if pid in lined_up_ids:
                continue  # Correctly lined up
            # Find the worst lined-up player in the same position
            pos = benched["position"]
            worst_in_pos = None
            for lid, lined in actually_lined.items():
                if (
                    lined["position"] == pos
                    and lid not in optimal_ids
                    and (worst_in_pos is None or lined["pts"] < worst_in_pos["pts"])
                ):
                    worst_in_pos = lined

            if worst_in_pos and benched["pts"] > worst_in_pos["pts"]:
                diffs.append(
                    MissedCall(
                        position=pos,
                        benched_name=benched["name"],
                        benched_points=benched["pts"],
                        lined_up_name=worst_in_pos["name"],
                        lined_up_points=worst_in_pos["pts"],
                    )
                )

        # Sort by biggest diff, return top 3
        diffs.sort(key=lambda d: d.benched_points - d.lined_up_points, reverse=True)
        return diffs[:3]

    async def _validate_deadline(self, matchday: object, season_id: int) -> None:
        """Check that the deadline hasn't passed."""
        now = datetime.now(UTC)

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
            deadline = deadline.replace(tzinfo=UTC)

        if now >= deadline:
            raise BusinessRuleError("El plazo para enviar la alineacion ha finalizado")

    def _validate_positions(self, players: list[LineupPlayerSlot], vf: object) -> None:
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
            raise BusinessRuleError(f"Jugadores no pertenecen a tu plantilla: {not_owned}")

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
