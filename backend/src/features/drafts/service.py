from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from src.features.drafts.repository import DraftRepository, WishlistRepository
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
    DraftTeamOption,
    PlayerDraftStats,
    PlayerSearchItem,
    PlayerSearchResponse,
    ReorderPicksResponse,
)
from src.features.drafts.websocket import draft_ws_manager
from src.features.drafts.wishlist_schemas import (
    AdminWishlistResponse,
    WishlistPlayerItem,
    WishlistResponse,
    WishlistUpsertRequest,
)
from src.features.seasons.repository import SeasonRepository
from src.shared.permissions import Perm

MAX_AUTO_PICK_CHAIN = 30
"""Upper bound for consecutive auto-picks in a single hook invocation.

A normal draft tops out at ~338 picks (13 participants x 26). Real chains
stay in the 1-3 range; the limit only matters as a defensive guard
against a misconfigured wishlist that would otherwise loop forever."""


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
            id=draft.id,
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
        user: dict,
        participant_id: int | None = None,
        origin: str = "manual",
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

        # Authorization: admins / DRAFT permission holders can pick for
        # anyone (including the participant whose turn it is). A regular
        # user is only allowed to confirm their own pick AND only when the
        # turn is actually theirs. Auto-pick (origin='auto') is driven by
        # the wishlist engine and bypasses the per-user check — the call
        # site already enforced that the wishlist belongs to the
        # participant whose turn it is.
        is_privileged = bool(user.get("is_admin")) or bool(
            (user.get("permissions") or 0) & Perm.DRAFT
        )
        if origin == "auto":
            is_privileged = True
        if not is_privileged:
            try:
                caller_user_id = int(user.get("sub") or 0)
            except (TypeError, ValueError):
                caller_user_id = 0
            caller_participant_id = next(
                (p.participant_id for p in participants if p.user_id == caller_user_id),
                None,
            )
            if caller_participant_id is None:
                raise AuthorizationError("No participas en esta temporada")
            if final_participant_id != caller_participant_id:
                raise AuthorizationError("Solo puedes hacer pick para ti mismo")
            if auto_participant_id != caller_participant_id:
                raise AuthorizationError("No es tu turno")

        pick = await self.repo.add_pick(
            draft_id=draft_id,
            participant_id=final_participant_id,
            player_id=player_id,
            round_number=round_number,
            pick_number=next_pick,
            origin=origin,
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
            origin=origin,
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

        # Auto-pick: if the next participant has a wishlist with at least
        # one available player, resolve their pick (and any chained ones)
        # before returning to the caller. The recursive call into add_pick
        # uses origin='auto' which bypasses the per-user authorization.
        # Failures here must not break the manual pick that already
        # committed — log and move on.
        if origin == "manual":
            try:
                await self._maybe_auto_pick(draft_id)
            except Exception:
                logger.exception("Auto-pick chain failed after manual pick in draft %d", draft_id)

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

    # -------------------------------------------------------------------
    # Auto-pick (wishlist-driven)
    # -------------------------------------------------------------------

    async def _maybe_auto_pick(self, draft_id: int) -> None:
        """Resolve auto-picks while the next participant has an active
        wishlist with at least one available candidate.

        Iterates (no recursion) so each step rereads draft state after the
        previous auto-pick's commit. Bound by MAX_AUTO_PICK_CHAIN.
        """
        wishlist_repo = WishlistRepository(self.repo.session)

        for _ in range(MAX_AUTO_PICK_CHAIN):
            draft = await self.repo.get_draft_by_id(draft_id)
            if draft is None:
                return

            participants = await self.repo.get_participants(draft.season_id)
            if not participants:
                return

            next_pick_number = await self.repo.get_max_pick_number(draft_id) + 1
            ordered_pids = [
                p.participant_id for p in sorted(participants, key=lambda x: x.draft_order or 999)
            ]
            next_participant_id = _get_participant_for_pick(
                next_pick_number, draft.draft_type, ordered_pids
            )

            player_id = await wishlist_repo.get_next_available_player(
                draft_id, next_participant_id
            )
            if player_id is None:
                return

            owner = next(
                (p for p in participants if p.participant_id == next_participant_id),
                None,
            )
            system_user = {
                "sub": owner.user_id if owner else 0,
                "is_admin": False,
                "permissions": 0,
            }

            try:
                await self.add_pick(
                    draft_id=draft_id,
                    player_id=player_id,
                    user=system_user,
                    participant_id=next_participant_id,
                    origin="auto",
                )
            except BusinessRuleError:
                # Player got picked by someone else between our SELECT and
                # the INSERT — restart the loop, the next iteration will
                # pick the new top of the wishlist.
                continue
        else:
            logger.warning(
                "Auto-pick chain reached MAX_AUTO_PICK_CHAIN=%d for draft %d",
                MAX_AUTO_PICK_CHAIN,
                draft_id,
            )

    # -------------------------------------------------------------------
    # Wishlist CRUD
    # -------------------------------------------------------------------

    async def _resolve_caller_participant_id(
        self,
        season_id: int,
        user: dict,
    ) -> int:
        try:
            caller_user_id = int(user.get("sub") or 0)
        except (TypeError, ValueError):
            caller_user_id = 0
        participants = await self.repo.get_participants(season_id)
        caller_participant_id = next(
            (p.participant_id for p in participants if p.user_id == caller_user_id),
            None,
        )
        if caller_participant_id is None:
            raise AuthorizationError("No participas en esta temporada")
        return caller_participant_id

    async def get_my_wishlist(self, draft_id: int, user: dict) -> WishlistResponse:
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)
        participant_id = await self._resolve_caller_participant_id(draft.season_id, user)
        wishlist_repo = WishlistRepository(self.repo.session)
        row = await wishlist_repo.get_wishlist_row(draft_id, participant_id)
        if row is None:
            return WishlistResponse(
                draft_id=draft_id,
                participant_id=participant_id,
                enabled=True,
                players=[],
            )
        return WishlistResponse(
            draft_id=row.draft_id,
            participant_id=row.participant_id,
            enabled=row.enabled,
            players=[
                WishlistPlayerItem(
                    player_id=p.player_id,
                    display_name=p.display_name,
                    position=p.position,
                    team_name=p.team_name,
                    photo_path=p.photo_path,
                    is_already_picked=p.is_already_picked,
                    priority=p.priority,
                )
                for p in row.players
            ],
        )

    async def upsert_my_wishlist(
        self,
        draft_id: int,
        user: dict,
        payload: WishlistUpsertRequest,
    ) -> WishlistResponse:
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)
        participant_id = await self._resolve_caller_participant_id(draft.season_id, user)

        # Reject duplicates eagerly — the UNIQUE on (wishlist_id, player_id)
        # would catch it but the message would be DB-flavoured.
        if len(set(payload.player_ids)) != len(payload.player_ids):
            raise BusinessRuleError("La lista contiene jugadores duplicados")

        wishlist_repo = WishlistRepository(self.repo.session)
        if payload.player_ids:
            valid = await wishlist_repo.validate_players_belong_to_season(
                draft.season_id, payload.player_ids
            )
            invalid = [pid for pid in payload.player_ids if pid not in valid]
            if invalid:
                raise BusinessRuleError(
                    f"Los siguientes jugadores no pertenecen a esta temporada "
                    f"o no están disponibles: {invalid}"
                )

        row = await wishlist_repo.upsert_wishlist(
            draft_id=draft_id,
            participant_id=participant_id,
            enabled=payload.enabled,
            player_ids=payload.player_ids,
        )
        await self.repo.session.commit()

        return WishlistResponse(
            draft_id=row.draft_id,
            participant_id=row.participant_id,
            enabled=row.enabled,
            players=[
                WishlistPlayerItem(
                    player_id=p.player_id,
                    display_name=p.display_name,
                    position=p.position,
                    team_name=p.team_name,
                    photo_path=p.photo_path,
                    is_already_picked=p.is_already_picked,
                    priority=p.priority,
                )
                for p in row.players
            ],
        )

    async def toggle_my_wishlist(
        self,
        draft_id: int,
        user: dict,
        enabled: bool,
    ) -> WishlistResponse:
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)
        participant_id = await self._resolve_caller_participant_id(draft.season_id, user)
        wishlist_repo = WishlistRepository(self.repo.session)
        existing = await wishlist_repo.get_wishlist_row(draft_id, participant_id)
        if existing is None:
            await wishlist_repo.upsert_wishlist(
                draft_id=draft_id,
                participant_id=participant_id,
                enabled=enabled,
                player_ids=[],
            )
        else:
            await wishlist_repo.set_enabled(draft_id, participant_id, enabled)
        await self.repo.session.commit()
        return await self.get_my_wishlist(draft_id, user)

    async def get_all_wishlists_admin(
        self,
        draft_id: int,
    ) -> list[AdminWishlistResponse]:
        """Return metadata-only summaries for every wishlist in *draft_id*.

        The admin sees who has configured a wishlist, whether it's
        active and how many entries it contains, but NEVER the player
        list — the contents are private to each participant.
        """
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)
        wishlist_repo = WishlistRepository(self.repo.session)
        rows = await wishlist_repo.list_for_admin(draft_id)
        return [
            AdminWishlistResponse(
                participant_id=r.participant_id,
                display_name=r.display_name,
                enabled=r.enabled,
                total=r.total,
            )
            for r in rows
        ]

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

        # NOTE: do NOT trigger _maybe_auto_pick here. If the deleted pick
        # was itself an auto-pick, the participant's wishlist still has
        # that same player as the top available candidate — re-firing
        # would re-insert the same pick_number with the same player,
        # producing a loop (admin deletes -> auto-pick recreates ->
        # admin deletes again). Deletions are an explicit manual
        # override; the next manual pick from any participant will
        # re-engage the auto-pick chain naturally.
        return DeletePickResponse(deleted_pick_number=pick_number)

    async def list_teams(self, draft_id: int) -> list[DraftTeamOption]:
        """Return the teams of the draft's season for the search filter."""
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)
        teams = await self.repo.list_teams(draft.season_id)
        return [DraftTeamOption(id=t.id, name=t.name) for t in teams]

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
