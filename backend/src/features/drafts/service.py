from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.drafts.repository import DraftRepository
from src.features.drafts.schemas import (
    AddPickResponse,
    CreateDraftResponse,
    DeletePickResponse,
    DraftDetailResponse,
    DraftListResponse,
    DraftParticipant,
    DraftPickEntry,
    DraftSummary,
    PlayerSearchItem,
    PlayerSearchResponse,
    ReorderPicksResponse,
)
from src.features.seasons.repository import SeasonRepository


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

        return AddPickResponse(
            pick_number=pk.pick_number,
            round_number=pk.round_number,
            participant_id=pk.participant_id,
            display_name=pk.display_name,
            player_name=pk.player_name,
            position=pk.position,
            team_name=pk.team_name,
        )

    async def delete_pick(
        self,
        draft_id: int,
        pick_number: int,
    ) -> DeletePickResponse:
        draft = await self.repo.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("Draft", draft_id)

        deleted = await self.repo.delete_pick(draft_id, pick_number)
        if not deleted:
            raise NotFoundError("Pick", pick_number)

        await self.repo.session.commit()
        return DeletePickResponse(deleted_pick_number=pick_number)

    async def search_players(
        self,
        draft_id: int,
        query: str,
        position: str | None,
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
