from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from src.features.drafts.repository import DraftRepository
from src.features.drafts.schemas import (
    AddPickResponse,
    CreateDraftResponse,
    DeletePickResponse,
    DraftDetailResponse,
    DraftListResponse,
    DraftParticipant,
    DraftPickEntry,
    DraftPlayerStatsResponse,
    DraftSummary,
    PlayerDraftStats,
    PlayerSearchItem,
    PlayerSearchResponse,
    ReorderPicksResponse,
)
from src.features.drafts.websocket import draft_ws_manager
from src.features.seasons.repository import SeasonRepository
from src.shared.permissions import Perm


def _get_participant_for_pick(
    pick_number: int,
    draft_type: str,
    ordered_participant_ids: list[int],
) -> int:
    """Return the participant_id for a given pick_number based on draft type.

    Snake: odd rounds go 1→N, even rounds go N→1.
    Linear: every round goes 1→N.
    """
    n = len(ordered_participant_ids)
    if n == 0:
        raise BusinessRuleError("No hay participantes")
    round_number = (pick_number - 1) // n + 1
    position_in_round = (pick_number - 1) % n

    if draft_type == "snake" and round_number % 2 == 0:
        # Even rounds are reversed
        position_in_round = n - 1 - position_in_round

    return ordered_participant_ids[position_in_round]


logger = logging.getLogger(__name__)


class DraftService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = DraftRepository(session)
        self.season_repo = SeasonRepository(session)

    async def list_drafts(self, season_id: int) -> DraftListResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        rows = await self.repo.list_for_season(season_id)
        return DraftListResponse(
            season_id=season_id,
            drafts=[
                DraftSummary(
                    id=r.id,
                    phase=r.phase,
                    draft_type=r.draft_type,
                    status=r.status,
                    total_picks=r.total_picks,
                    started_at=r.started_at,
                    completed_at=r.completed_at,
                )
                for r in rows
            ],
        )

    async def get_draft_detail(
        self,
        season_id: int,
        phase: str,
    ) -> DraftDetailResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        draft = await self.repo.get_draft(season_id, phase)
        if draft is None:
            raise NotFoundError("Draft", f"{season_id}/{phase}")

        participant_rows = await self.repo.get_participants(season_id)
        pick_rows = await self.repo.get_picks(draft.id)

        # Calculate next participant
        next_pid: int | None = None
        if participant_rows:
            ordered_pids = [
                p.participant_id
                for p in sorted(participant_rows, key=lambda x: x.draft_order or 999)
            ]
            next_pick = len(pick_rows) + 1
            next_pid = _get_participant_for_pick(next_pick, draft.draft_type, ordered_pids)

        return DraftDetailResponse(
            season_id=season_id,
            phase=draft.phase,
            draft_type=draft.draft_type,
            status=draft.status,
            started_at=draft.started_at,
            completed_at=draft.completed_at,
            participants=[
                DraftParticipant(
                    participant_id=p.participant_id,
                    user_id=p.user_id,
                    display_name=p.display_name,
                    draft_order=p.draft_order,
                )
                for p in participant_rows
            ],
            picks=[
                DraftPickEntry(
                    id=pk.id,
                    pick_number=pk.pick_number,
                    round_number=pk.round_number,
                    participant_id=pk.participant_id,
                    display_name=pk.display_name,
                    draft_order=pk.draft_order,
                    player_id=pk.player_id,
                    player_name=pk.player_name,
                    position=pk.position,
                    team_name=pk.team_name,
                    photo_path=pk.photo_path,
                    dropped_player_name=pk.dropped_player_name,
                )
                for pk in pick_rows
            ],
            next_participant_id=next_pid,
        )

    # -------------------------------------------------------------------
    # Draft management (write operations)
    # -------------------------------------------------------------------

    async def update_draft_order(
        self,
        season_id: int,
        orders: list[tuple[int, int]],
    ) -> None:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        participants = await self.repo.get_participants(season_id)
        valid_ids = {p.participant_id for p in participants}
        for pid, _ in orders:
            if pid not in valid_ids:
                raise BusinessRuleError(
                    f"Participante {pid} no pertenece a la temporada {season_id}"
                )

        await self.repo.update_participant_orders(season_id, orders)
        await self.repo.session.commit()

    async def create_draft(
        self,
        season_id: int,
        phase: str,
        draft_type: str,
    ) -> CreateDraftResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        if phase not in ("preseason", "winter"):
            raise BusinessRuleError("La fase debe ser 'preseason' o 'winter'")
        if draft_type not in ("snake", "linear"):
            raise BusinessRuleError("El tipo debe ser 'snake' o 'linear'")
        if phase == "winter" and season.kind != "league":
            raise BusinessRuleError(
                "El draft de invierno solo aplica a temporadas de Liga (los torneos cortos no tienen mercado invernal)"
            )

        existing = await self.repo.get_draft(season_id, phase)
        if existing is not None:
            raise BusinessRuleError(f"Ya existe un draft para temporada {season_id} fase {phase}")

        draft = await self.repo.create_draft(season_id, phase, draft_type)
        await self.repo.session.commit()

        return CreateDraftResponse(
            id=draft.id,
            season_id=draft.season_id,
            phase=draft.phase,
            draft_type=draft.draft_type,
            status=draft.status,
        )

    async def add_pick(
        self,
        draft_id: int,
        player_id: int,
        participant_id: int | None = None,
    ) -> AddPickResponse:
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)

        # Check player not already picked
        picked = await self.repo.get_picked_player_ids(draft_id)
        if player_id in picked:
            raise BusinessRuleError("Este jugador ya fue seleccionado en este draft")

        participants = await self.repo.get_participants(draft.season_id)
        num_participants = len(participants)
        if num_participants == 0:
            raise BusinessRuleError("No hay participantes en esta temporada")

        # Calculate pick_number and round_number
        next_pick = await self.repo.get_max_pick_number(draft_id) + 1
        round_number = (next_pick - 1) // num_participants + 1

        # Auto-determine participant based on draft type + order
        ordered_pids = [
            p.participant_id for p in sorted(participants, key=lambda x: x.draft_order or 999)
        ]
        auto_participant_id = _get_participant_for_pick(next_pick, draft.draft_type, ordered_pids)

        # Use provided participant_id if given, otherwise auto
        final_participant_id = participant_id or auto_participant_id

        # Validate participant belongs to the season
        valid_ids = {p.participant_id for p in participants}
        if final_participant_id not in valid_ids:
            raise BusinessRuleError("Participante no valido para esta temporada")

        pick = await self.repo.add_pick(
            draft_id=draft_id,
            participant_id=final_participant_id,
            player_id=player_id,
            round_number=round_number,
            pick_number=next_pick,
        )
        await self.repo.session.commit()

        # Fetch pick details for response
        pick_rows = await self.repo.get_picks(draft_id)
        pk = next(p for p in pick_rows if p.pick_number == pick.pick_number)

        response = AddPickResponse(
            pick_number=pk.pick_number,
            round_number=pk.round_number,
            participant_id=pk.participant_id,
            display_name=pk.display_name,
            player_id=pk.player_id,
            player_name=pk.player_name,
            position=pk.position,
            team_name=pk.team_name,
            photo_path=pk.photo_path,
        )

        # Broadcast to all connected WebSocket clients for this draft
        next_pick_number = next_pick + 1
        next_pid = _get_participant_for_pick(next_pick_number, draft.draft_type, ordered_pids)
        await draft_ws_manager.broadcast(
            draft_id,
            {
                "type": "pick_added",
                "pick": response.model_dump(),
                "next_participant_id": next_pid,
            },
        )

        # Notify Telegram (best-effort, never blocks the pick)
        try:
            next_participant_name: str | None = None
            if next_pid is not None:
                nxt = next((p for p in participants if p.participant_id == next_pid), None)
                next_participant_name = nxt.display_name if nxt else None
            await self._notify_pick_telegram(
                draft.season_id,
                pick=response,
                next_pick_number=next_pick_number,
                next_participant_name=next_participant_name,
            )
        except Exception:
            logger.exception("Failed to notify draft pick via Telegram")

        return response

    async def _notify_pick_telegram(
        self,
        season_id: int,
        pick: AddPickResponse,
        next_pick_number: int,
        next_participant_name: str | None,
    ) -> None:
        """Best-effort Telegram broadcast of a single draft pick.

        Sends a photo with HTML caption when the player has a stored photo;
        otherwise falls back to a plain text message with the same content.
        """
        from pathlib import Path

        from src.features.telegram.client import TelegramClient
        from src.shared.country_flags import flag_emoji_for
        from src.shared.models.season import Season

        season = await self.repo.session.get(Season, season_id)
        if season is None or not season.draft_telegram_chat_id:
            return

        flag = flag_emoji_for(pick.team_name)
        player_line = f"{flag} <b>{pick.player_name}</b>" if flag else f"<b>{pick.player_name}</b>"
        text = (
            f"🟢 <b>Pick #{pick.pick_number}</b> · Ronda {pick.round_number}\n"
            f"<b>{pick.display_name}</b> eligió: {player_line} "
            f"({pick.position}, {pick.team_name})"
        )
        if next_participant_name:
            text += f"\n\n➡️ Siguiente: <b>{next_participant_name}</b> — Pick #{next_pick_number}"

        # Try to attach the player photo when available on disk.
        photo_bytes: bytes | None = None
        if pick.photo_path:
            backend_root = Path(__file__).resolve().parents[3]
            photo_file = backend_root / "static" / pick.photo_path
            if photo_file.exists():
                try:
                    photo_bytes = photo_file.read_bytes()
                except OSError as exc:
                    logger.warning("Could not read player photo %s: %s", photo_file, exc)

        async with TelegramClient() as client:
            if photo_bytes:
                await client.send_photo(
                    season.draft_telegram_chat_id,
                    photo_bytes,
                    caption=text,
                    filename=f"player_{pick.player_id}.webp",
                    message_thread_id=season.draft_telegram_thread_id,
                )
            else:
                await client.send_message(
                    season.draft_telegram_chat_id,
                    text,
                    message_thread_id=season.draft_telegram_thread_id,
                )

    async def delete_pick(
        self,
        draft_id: int,
        pick_number: int,
        user: dict,
    ) -> DeletePickResponse:
        """Delete a draft pick with role-based authorization.

        Allowed callers:
        * Admin (``is_admin``) or holder of the ``DRAFT`` permission bit:
          can delete *any* pick.
        * Otherwise the caller must own the pick AND it must be the last
          one made in the draft (the "undo my last pick" rule). This
          prevents a normal user from rewriting history once someone else
          has picked after them.

        After deleting, broadcasts a ``pick_deleted`` event over the draft
        WebSocket so connected clients can resync state and turn order.
        """
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)

        picks = await self.repo.get_picks(draft_id)
        target = next((p for p in picks if p.pick_number == pick_number), None)
        if target is None:
            raise NotFoundError("Pick", pick_number)

        is_privileged = bool(user.get("is_admin")) or bool(
            (user.get("permissions") or 0) & Perm.DRAFT
        )
        if not is_privileged:
            try:
                caller_user_id = int(user.get("sub") or 0)
            except (TypeError, ValueError):
                caller_user_id = 0

            participants = await self.repo.get_participants(draft.season_id)
            caller_participant_id = next(
                (p.participant_id for p in participants if p.user_id == caller_user_id),
                None,
            )
            if caller_participant_id is None:
                raise AuthorizationError("No participas en esta temporada")
            if target.participant_id != caller_participant_id:
                raise AuthorizationError("Solo puedes eliminar tus propios picks")
            last_pick_number = max(p.pick_number for p in picks)
            if pick_number != last_pick_number:
                raise AuthorizationError(
                    "Solo puedes eliminar tu último pick mientras nadie haya fichado después"
                )

        deleted = await self.repo.delete_pick(draft_id, pick_number)
        if not deleted:
            raise NotFoundError("Pick", pick_number)
        await self.repo.session.commit()

        # Recompute the "next participant" so connected clients can show the
        # correct turn after the undo.
        participants = await self.repo.get_participants(draft.season_id)
        ordered_pids = [
            p.participant_id for p in sorted(participants, key=lambda x: x.draft_order or 999)
        ]
        next_pid = (
            _get_participant_for_pick(pick_number, draft.draft_type, ordered_pids)
            if ordered_pids
            else None
        )
        await draft_ws_manager.broadcast(
            draft_id,
            {
                "type": "pick_deleted",
                "pick_number": pick_number,
                "participant_id": target.participant_id,
                "player_id": target.player_id,
                "next_participant_id": next_pid,
                "next_pick_number": pick_number,
            },
        )

        return DeletePickResponse(deleted_pick_number=pick_number)

    async def search_players(
        self,
        draft_id: int,
        query: str,
        position: str | None,
        team_id: int | None = None,
    ) -> PlayerSearchResponse:
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)

        picked = await self.repo.get_picked_player_ids(draft_id)
        rows = await self.repo.search_players(
            season_id=draft.season_id,
            picked_ids=picked,
            query=query,
            position=position,
            team_id=team_id,
        )

        return PlayerSearchResponse(
            players=[
                PlayerSearchItem(
                    id=r.id,
                    display_name=r.display_name,
                    position=r.position,
                    team_name=r.team_name,
                    photo_path=r.photo_path,
                    is_already_picked=r.is_already_picked,
                )
                for r in rows
            ]
        )

    async def get_player_stats_for_draft(self, draft_id: int) -> DraftPlayerStatsResponse:
        """Get advanced stats for all unpicked players (admin use during live draft)."""
        from src.features.stats.repository_advanced import AdvancedStatsRepository
        from src.features.stats.service_advanced import _ewma

        # 1. Get draft to find season_id
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)
        season_id = draft.season_id

        # 2. Get picked player IDs
        picked_ids = await self.repo.get_picked_player_ids(draft_id)

        # 3. Get season stats using the advanced stats repo
        adv_repo = AdvancedStatsRepository(self.repo.session)

        player_stats = await adv_repo.get_player_season_stats_for_predictions(season_id)
        recent_points = await adv_repo.get_player_recent_points(season_id, n=5)
        starter_pcts = await adv_repo.get_player_starter_pct(season_id, n=5)

        # 4. Build response (only unpicked players)
        players: dict[str, PlayerDraftStats] = {}
        by_position: dict[str, list[tuple[int, float]]] = {}

        for player_id, stats in player_stats.items():
            if player_id in picked_ids:
                continue

            avg_pts = stats["avg_pts"]
            pts_list = recent_points.get(player_id, [])
            form_5 = round(_ewma(pts_list), 1) if len(pts_list) >= 2 else None
            form_val = form_5 if form_5 is not None else avg_pts

            if avg_pts > 0:
                if form_val > avg_pts * 1.1:
                    trend = "rising"
                elif form_val < avg_pts * 0.9:
                    trend = "falling"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            starter_pct = starter_pcts.get(player_id, 1.0)

            players[str(player_id)] = PlayerDraftStats(
                player_id=player_id,
                avg_pts=round(avg_pts, 1),
                std_dev=round(stats["std_dev"], 1),
                form_5=form_5,
                trend=trend,
                matchdays_played=stats["matchdays_played"],
                starter_pct=round(starter_pct * 100, 0),
            )

            # Score for suggestions: avg * starter_factor * trend_factor
            starter_factor = 1.0 if starter_pct >= 0.8 else 0.7
            trend_factor = 1.1 if trend == "rising" else (0.9 if trend == "falling" else 1.0)
            score = avg_pts * starter_factor * trend_factor

            position = stats["position"]
            if position not in by_position:
                by_position[position] = []
            by_position[position].append((player_id, score))

        # 5. Build suggestions (top 5 per position)
        suggestions: dict[str, list[int]] = {}
        for pos in ["POR", "DEF", "MED", "DEL"]:
            pos_list = by_position.get(pos, [])
            pos_list.sort(key=lambda x: x[1], reverse=True)
            suggestions[pos] = [pid for pid, _ in pos_list[:5]]

        return DraftPlayerStatsResponse(players=players, suggestions=suggestions)

    async def reorder_picks(
        self,
        draft_id: int,
        pick_ids: list[int],
    ) -> ReorderPicksResponse:
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)

        # Validate that pick_ids match existing picks
        existing_picks = await self.repo.get_picks(draft_id)
        existing_ids = {p.id for p in existing_picks}
        provided_ids = set(pick_ids)

        if existing_ids != provided_ids:
            raise BusinessRuleError("La lista de picks no coincide con los picks existentes")

        participants = await self.repo.get_participants(draft.season_id)
        num_participants = len(participants)
        if num_participants == 0:
            raise BusinessRuleError("No hay participantes en esta temporada")

        # Build reorder entries: (pick_id, pick_number, round)
        # participant_id is NOT changed — it's a historical fact (who picked the player)
        # Within each round, picks are sorted by draft_order (snake reverses even rounds)
        is_winter = draft.phase == "winter"

        if is_winter:
            entries: list[tuple[int, int, int]] = [
                (pick_id, i + 1, 1) for i, pick_id in enumerate(pick_ids)
            ]
        else:
            pick_map = {p.id: p for p in existing_picks}
            participant_order = {p.participant_id: (p.draft_order or 999) for p in participants}

            # Assign rounds based on position in input order
            rounds: dict[int, list[int]] = {}
            for i, pick_id in enumerate(pick_ids):
                rnd = i // num_participants + 1
                rounds.setdefault(rnd, []).append(pick_id)

            # Sort within each round by draft_order
            entries = []
            pick_num = 1
            for rnd in sorted(rounds):
                round_picks = rounds[rnd]
                reverse = draft.draft_type == "snake" and rnd % 2 == 0
                round_picks.sort(
                    key=lambda pid: participant_order.get(pick_map[pid].participant_id, 999),
                    reverse=reverse,
                )
                for pid in round_picks:
                    entries.append((pid, pick_num, rnd))
                    pick_num += 1

        await self.repo.reorder_picks(draft_id, entries)
        await self.repo.session.commit()

        return ReorderPicksResponse(reordered=len(pick_ids))
