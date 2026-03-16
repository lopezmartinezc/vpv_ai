from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, update
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
        self,
        season_id: int,
        phase: str,
    ) -> Draft | None:
        stmt = select(Draft).where(
            Draft.season_id == season_id,
            Draft.phase == phase,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_participants(
        self,
        season_id: int,
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

    # -------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------

    async def update_participant_orders(
        self,
        season_id: int,
        orders: list[tuple[int, int]],
    ) -> None:
        for participant_id, draft_order in orders:
            await self.session.execute(
                update(SeasonParticipant)
                .where(
                    SeasonParticipant.id == participant_id,
                    SeasonParticipant.season_id == season_id,
                )
                .values(draft_order=draft_order)
            )

    async def create_draft(
        self,
        season_id: int,
        phase: str,
        draft_type: str,
    ) -> Draft:
        draft = Draft(
            season_id=season_id,
            phase=phase,
            draft_type=draft_type,
            status="pending",
        )
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def get_draft_by_id(self, draft_id: int) -> Draft | None:
        stmt = select(Draft).where(Draft.id == draft_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_pick(
        self,
        draft_id: int,
        participant_id: int,
        player_id: int,
        round_number: int,
        pick_number: int,
    ) -> DraftPick:
        pick = DraftPick(
            draft_id=draft_id,
            participant_id=participant_id,
            player_id=player_id,
            round_number=round_number,
            pick_number=pick_number,
        )
        self.session.add(pick)
        await self.session.flush()
        return pick

    async def delete_pick(self, draft_id: int, pick_number: int) -> bool:
        result = await self.session.execute(
            delete(DraftPick).where(
                DraftPick.draft_id == draft_id,
                DraftPick.pick_number == pick_number,
            )
        )
        return result.rowcount > 0

    async def get_picked_player_ids(self, draft_id: int) -> set[int]:
        stmt = select(DraftPick.player_id).where(DraftPick.draft_id == draft_id)
        result = await self.session.execute(stmt)
        return {row[0] for row in result.all()}

    async def get_pick_count(self, draft_id: int) -> int:
        stmt = select(func.count(DraftPick.id)).where(DraftPick.draft_id == draft_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_max_pick_number(self, draft_id: int) -> int:
        stmt = select(func.coalesce(func.max(DraftPick.pick_number), 0)).where(
            DraftPick.draft_id == draft_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def search_players(
        self,
        season_id: int,
        picked_ids: set[int],
        query: str,
        position: str | None,
        limit: int = 20,
    ) -> list[PlayerSearchRow]:
        stmt = (
            select(
                Player.id,
                Player.display_name,
                Player.position,
                Team.name.label("team_name"),
                Player.photo_path,
            )
            .join(Team, Player.team_id == Team.id)
            .where(Player.season_id == season_id)
        )

        if query:
            stmt = stmt.where(Player.display_name.ilike(f"%{query}%"))
        if position:
            stmt = stmt.where(Player.position == position)

        stmt = stmt.order_by(Player.display_name.asc()).limit(limit)
        result = await self.session.execute(stmt)

        return [
            PlayerSearchRow(
                id=row.id,
                display_name=row.display_name,
                position=row.position,
                team_name=row.team_name,
                photo_path=row.photo_path,
                is_already_picked=row.id in picked_ids,
            )
            for row in result.all()
        ]


@dataclass
class PlayerSearchRow:
    id: int
    display_name: str
    position: str
    team_name: str
    photo_path: str | None
    is_already_picked: bool
