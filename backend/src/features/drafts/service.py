from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.drafts.repository import DraftRepository
from src.features.drafts.schemas import (
    DraftDetailResponse,
    DraftListResponse,
    DraftParticipant,
    DraftPickEntry,
    DraftSummary,
)
from src.features.seasons.repository import SeasonRepository


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
                    pick_number=pk.pick_number,
                    round_number=pk.round_number,
                    participant_id=pk.participant_id,
                    display_name=pk.display_name,
                    draft_order=pk.draft_order,
                    player_name=pk.player_name,
                    position=pk.position,
                    team_name=pk.team_name,
                )
                for pk in pick_rows
            ],
        )
