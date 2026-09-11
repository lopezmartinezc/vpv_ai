from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from src.features.drafts.schemas import DraftDetailResponse
from src.features.stats.schemas_draft import DraftValuePlayer

from .errors import AssistantError
from .schemas import Card, Revision, ViewContext


class RosterPlayer(BaseModel):
    id: int
    owner_id: int | None
    is_available: bool
    name: str
    team: str
    position: str


class Formation(BaseModel):
    name: str
    defenders: int
    midfielders: int
    forwards: int


class Snapshot(BaseModel):
    captured_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    draft: DraftDetailResponse
    pool_size: int
    season_status: str
    players: list[DraftValuePlayer]
    roster: list[RosterPlayer]
    formations: list[Formation]
    participation: str

    def revision(self) -> Revision:
        draft_data = self.model_dump_json(exclude={"players", "participation", "captured_at"})
        board_data = self.model_dump_json(include={"players", "participation"})
        return Revision(
            draft=hashlib.sha256(draft_data.encode()).hexdigest(),
            board=hashlib.sha256(board_data.encode()).hexdigest(),
            at=self.captured_at,
            pick_count=len(self.draft.picks),
        )

    def available_ids(self) -> set[int]:
        picked = {p.player_id for p in self.draft.picks}
        return {p.id for p in self.roster if p.is_available and p.owner_id is None} - picked

    def target(self, user_id: int, view: ViewContext) -> int | None:
        participants = self.draft.participants
        if view.participant_id is not None:
            if not any(p.participant_id == view.participant_id for p in participants):
                raise AssistantError("INVALID_PARTICIPANT", "Participante ajeno al draft.")
            return view.participant_id
        return next((p.participant_id for p in participants if p.user_id == user_id), None)

    def validate_view(self, view: ViewContext) -> None:
        ids = {p.id for p in self.roster}
        if not set(view.selected_player_ids) <= ids:
            raise AssistantError("INVALID_PLAYER", "Jugador ajeno a la temporada del draft.")

        if not set(view.selected_player_ids) <= {p.player_id for p in self.players}:
            raise AssistantError("PLAYER_WITHOUT_DATA", "Jugador sin datos en este tablero.")

    def card(self, player: DraftValuePlayer) -> Card:
        available = self.available_ids()
        lower = sorted(
            (
                p.priority
                for p in self.players
                if p.player_id in available
                and p.position == player.position
                and p.priority is not None
                and player.priority is not None
                and p.player_id != player.player_id
                and p.priority <= player.priority
            ),
            reverse=True,
        )
        gap = player.priority - lower[0] if lower and player.priority is not None else None
        return Card(
            player_id=player.player_id,
            name=player.display_name,
            position=player.position,
            team=player.team_name,
            available=player.player_id in available,
            priority=player.priority,
            priority_base=player.priority_base,
            vorp=player.vorp,
            participation=player.participation,
            available_gap=gap,
            avg_points=player.avg_points,
            games_played=player.games_played,
            seasons_played=player.seasons_played,
            availability=player.availability,
            exp_games_remaining=player.exp_games_remaining,
            is_new=player.is_new,
            team_changed=player.team_changed,
            position_changed=player.position_changed,
            ref_season_name=player.ref_season_name,
            previous_season=player.previous_season,
            tags=player.tags,
            evidence_id=f"player:{player.player_id}",
        )
