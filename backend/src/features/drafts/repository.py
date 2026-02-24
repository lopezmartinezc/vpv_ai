from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.draft import Draft, DraftPick
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.team import Team
from src.shared.models.user import User


@dataclass
class DraftSummaryRow:
    id: int
    phase: str
    draft_type: str
    status: str
    total_picks: int
    started_at: datetime | None
    completed_at: datetime | None


@dataclass
class DraftParticipantRow:
    participant_id: int
    display_name: str
    draft_order: int | None


@dataclass
class DraftPickRow:
    pick_number: int
    round_number: int
    participant_id: int
    display_name: str
    draft_order: int | None
    player_name: str
    position: str
    team_name: str


class DraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_season(self, season_id: int) -> list[DraftSummaryRow]:
        pick_count = (
            select(
                DraftPick.draft_id,
                func.count(DraftPick.id).label("total_picks"),
            )
            .group_by(DraftPick.draft_id)
            .subquery()
        )

        stmt = (
            select(
                Draft.id,
                Draft.phase,
                Draft.draft_type,
                Draft.status,
                func.coalesce(pick_count.c.total_picks, 0).label("total_picks"),
                Draft.started_at,
                Draft.completed_at,
            )
            .outerjoin(pick_count, pick_count.c.draft_id == Draft.id)
            .where(Draft.season_id == season_id)
            .order_by(Draft.id.asc())
        )

        result = await self.session.execute(stmt)
        return [
            DraftSummaryRow(
                id=row.id,
                phase=row.phase,
                draft_type=row.draft_type,
                status=row.status,
                total_picks=row.total_picks,
                started_at=row.started_at,
                completed_at=row.completed_at,
            )
            for row in result.all()
        ]

    async def get_draft(
        self, season_id: int, phase: str,
    ) -> Draft | None:
        stmt = select(Draft).where(
            Draft.season_id == season_id,
            Draft.phase == phase,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_participants(
        self, season_id: int,
    ) -> list[DraftParticipantRow]:
        stmt = (
            select(
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                SeasonParticipant.draft_order,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .where(SeasonParticipant.season_id == season_id)
            .order_by(SeasonParticipant.draft_order.asc().nulls_last())
        )

        result = await self.session.execute(stmt)
        return [
            DraftParticipantRow(
                participant_id=row.participant_id,
                display_name=row.display_name,
                draft_order=row.draft_order,
            )
            for row in result.all()
        ]

    async def get_picks(self, draft_id: int) -> list[DraftPickRow]:
        stmt = (
            select(
                DraftPick.pick_number,
                DraftPick.round_number,
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                SeasonParticipant.draft_order,
                Player.display_name.label("player_name"),
                Player.position,
                Team.name.label("team_name"),
            )
            .join(
                SeasonParticipant,
                DraftPick.participant_id == SeasonParticipant.id,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .join(Player, DraftPick.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .where(DraftPick.draft_id == draft_id)
            .order_by(DraftPick.pick_number.asc())
        )

        result = await self.session.execute(stmt)
        return [
            DraftPickRow(
                pick_number=row.pick_number,
                round_number=row.round_number,
                participant_id=row.participant_id,
                display_name=row.display_name,
                draft_order=row.draft_order,
                player_name=row.player_name,
                position=row.position,
                team_name=row.team_name,
            )
            for row in result.all()
        ]
