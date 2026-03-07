from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.team import Team
from src.shared.models.user import User


@dataclass
class PlayerRow:
    id: int
    display_name: str
    slug: str
    position: str
    team_id: int
    team_name: str
    owner_name: str | None
    is_available: bool


@dataclass
class PlayerDetailRow:
    id: int
    display_name: str
    team_id: int
    team_name: str
    position: str
    season_id: int


class PlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_players(
        self,
        season_id: int,
        search: str | None,
        team_id: int | None,
    ) -> list[PlayerRow]:
        stmt = (
            select(
                Player.id,
                Player.display_name,
                Player.slug,
                Player.position,
                Player.team_id,
                Team.name.label("team_name"),
                User.display_name.label("owner_name"),
                Player.is_available,
            )
            .join(Team, Player.team_id == Team.id)
            .outerjoin(SeasonParticipant, Player.owner_id == SeasonParticipant.id)
            .outerjoin(User, SeasonParticipant.user_id == User.id)
            .where(Player.season_id == season_id)
        )

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                Player.display_name.ilike(pattern) | Player.slug.ilike(pattern)
            )

        if team_id is not None:
            stmt = stmt.where(Player.team_id == team_id)

        stmt = stmt.order_by(Player.display_name)

        result = await self.session.execute(stmt)
        return [
            PlayerRow(
                id=row.id,
                display_name=row.display_name,
                slug=row.slug,
                position=row.position,
                team_id=row.team_id,
                team_name=row.team_name,
                owner_name=row.owner_name,
                is_available=row.is_available,
            )
            for row in result.all()
        ]

    async def list_teams(self, season_id: int) -> list[Team]:
        stmt = (
            select(Team)
            .where(Team.season_id == season_id)
            .order_by(Team.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_player_detail(self, player_id: int) -> PlayerDetailRow | None:
        stmt = (
            select(
                Player.id,
                Player.display_name,
                Player.team_id,
                Team.name.label("team_name"),
                Player.position,
                Player.season_id,
            )
            .join(Team, Player.team_id == Team.id)
            .where(Player.id == player_id)
        )
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        return PlayerDetailRow(
            id=row.id,
            display_name=row.display_name,
            team_id=row.team_id,
            team_name=row.team_name,
            position=row.position,
            season_id=row.season_id,
        )

    async def team_belongs_to_season(self, team_id: int, season_id: int) -> bool:
        stmt = select(Team.id).where(
            Team.id == team_id,
            Team.season_id == season_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def update_player(
        self,
        player_id: int,
        team_id: int | None,
        position: str | None,
    ) -> None:
        values: dict = {}
        if team_id is not None:
            values["team_id"] = team_id
        if position is not None:
            values["position"] = position
        if not values:
            return
        stmt = update(Player).where(Player.id == player_id).values(**values)
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_updated_player_detail(self, player_id: int) -> PlayerDetailRow | None:
        # Re-fetch after update so joined team_name is fresh.
        return await self.get_player_detail(player_id)
