from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.draft import Draft, DraftPick
from src.shared.models.draft_wishlist import DraftWishlist, DraftWishlistPlayer
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
    user_id: int
    display_name: str
    draft_order: int | None


@dataclass
class DraftPickRow:
    id: int
    pick_number: int
    round_number: int
    participant_id: int
    display_name: str
    draft_order: int | None
    player_id: int
    player_name: str
    position: str
    team_name: str
    photo_path: str | None
    dropped_player_name: str | None


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
                SeasonParticipant.user_id,
                User.display_name,
                SeasonParticipant.draft_order,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .where(
                SeasonParticipant.season_id == season_id,
                SeasonParticipant.is_active.is_(True),
            )
            .order_by(SeasonParticipant.draft_order.asc().nulls_last())
        )

        result = await self.session.execute(stmt)
        return [
            DraftParticipantRow(
                participant_id=row.participant_id,
                user_id=row.user_id,
                display_name=row.display_name,
                draft_order=row.draft_order,
            )
            for row in result.all()
        ]

    async def get_picks(self, draft_id: int) -> list[DraftPickRow]:
        from sqlalchemy.orm import aliased

        dropped_player = aliased(Player)

        stmt = (
            select(
                DraftPick.id,
                DraftPick.pick_number,
                DraftPick.round_number,
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
                SeasonParticipant.draft_order,
                DraftPick.player_id,
                Player.display_name.label("player_name"),
                Player.position,
                Team.name.label("team_name"),
                Player.photo_path,
                dropped_player.display_name.label("dropped_player_name"),
            )
            .join(
                SeasonParticipant,
                DraftPick.participant_id == SeasonParticipant.id,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .join(Player, DraftPick.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .outerjoin(dropped_player, DraftPick.dropped_player_id == dropped_player.id)
            .where(DraftPick.draft_id == draft_id)
            .order_by(DraftPick.pick_number.asc())
        )

        result = await self.session.execute(stmt)
        return [
            DraftPickRow(
                id=row.id,
                pick_number=row.pick_number,
                round_number=row.round_number,
                participant_id=row.participant_id,
                display_name=row.display_name,
                draft_order=row.draft_order,
                player_id=row.player_id,
                player_name=row.player_name,
                position=row.position,
                team_name=row.team_name,
                photo_path=row.photo_path,
                dropped_player_name=row.dropped_player_name,
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
        origin: str = "manual",
    ) -> DraftPick:
        pick = DraftPick(
            draft_id=draft_id,
            participant_id=participant_id,
            player_id=player_id,
            round_number=round_number,
            pick_number=pick_number,
            origin=origin,
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
        return result.rowcount > 0  # type: ignore[attr-defined]

    async def reorder_picks(
        self,
        draft_id: int,
        ordered_entries: list[tuple[int, int, int]],
    ) -> None:
        """Reorder all picks. Each entry: (pick_id, new_pick_number, new_round).

        participant_id is NOT changed — it's a historical fact (who picked the player).
        """
        # First set all pick_numbers to negative to avoid unique constraint conflicts
        for pick_id, new_pick_number, _ in ordered_entries:
            await self.session.execute(
                update(DraftPick)
                .where(DraftPick.id == pick_id, DraftPick.draft_id == draft_id)
                .values(pick_number=-new_pick_number)
            )
        # Then set to final positive values
        for pick_id, new_pick_number, new_round in ordered_entries:
            await self.session.execute(
                update(DraftPick)
                .where(DraftPick.id == pick_id, DraftPick.draft_id == draft_id)
                .values(
                    pick_number=new_pick_number,
                    round_number=new_round,
                )
            )

    async def list_teams(self, season_id: int) -> list[Team]:
        """List every team in *season_id*, ordered by name."""
        stmt = select(Team).where(Team.season_id == season_id).order_by(Team.name)
        result = await self.session.execute(stmt)
        return list(result.scalars())

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
        team_id: int | None = None,
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
            .where(
                Player.season_id == season_id,
                # Drop players dropped from the official squad — sync-rosters
                # flips is_available=False for them so they no longer appear
                # in draft search nor accidentally get picked.
                Player.is_available.is_(True),
            )
        )

        if query:
            stmt = stmt.where(Player.display_name.ilike(f"%{query}%"))
        if position:
            stmt = stmt.where(Player.position == position)
        if team_id is not None:
            stmt = stmt.where(Player.team_id == team_id)

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


@dataclass
class WishlistPlayerRow:
    player_id: int
    display_name: str
    position: str | None
    team_name: str | None
    photo_path: str | None
    priority: int
    is_already_picked: bool


@dataclass
class WishlistRow:
    wishlist_id: int
    draft_id: int
    participant_id: int
    enabled: bool
    players: list[WishlistPlayerRow]


@dataclass
class AdminWishlistRow:
    """Metadata-only summary for the admin audit view.

    Intentionally omits the list of players — see AdminWishlistResponse.
    """

    wishlist_id: int
    participant_id: int
    display_name: str
    enabled: bool
    total: int


class WishlistRepository:
    """Persistence layer for draft auto-pick wishlists.

    Kept as a sibling of DraftRepository so the existing class stays
    focused on picks and search; both share the same AsyncSession.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_wishlist_row(
        self,
        draft_id: int,
        participant_id: int,
    ) -> WishlistRow | None:
        wishlist_stmt = select(DraftWishlist).where(
            DraftWishlist.draft_id == draft_id,
            DraftWishlist.participant_id == participant_id,
        )
        wishlist = (await self.session.execute(wishlist_stmt)).scalar_one_or_none()
        if wishlist is None:
            return None

        rows = await self._fetch_player_rows(draft_id, wishlist.id)
        return WishlistRow(
            wishlist_id=wishlist.id,
            draft_id=wishlist.draft_id,
            participant_id=wishlist.participant_id,
            enabled=wishlist.enabled,
            players=rows,
        )

    async def upsert_wishlist(
        self,
        draft_id: int,
        participant_id: int,
        enabled: bool,
        player_ids: list[int],
    ) -> WishlistRow:
        existing_stmt = select(DraftWishlist).where(
            DraftWishlist.draft_id == draft_id,
            DraftWishlist.participant_id == participant_id,
        )
        wishlist = (await self.session.execute(existing_stmt)).scalar_one_or_none()
        if wishlist is None:
            wishlist = DraftWishlist(
                draft_id=draft_id,
                participant_id=participant_id,
                enabled=enabled,
            )
            self.session.add(wishlist)
            await self.session.flush()
        else:
            wishlist.enabled = enabled

        await self.session.execute(
            delete(DraftWishlistPlayer).where(DraftWishlistPlayer.wishlist_id == wishlist.id)
        )
        await self.session.flush()

        for priority, player_id in enumerate(player_ids):
            self.session.add(
                DraftWishlistPlayer(
                    wishlist_id=wishlist.id,
                    player_id=player_id,
                    priority=priority,
                )
            )
        await self.session.flush()

        rows = await self._fetch_player_rows(draft_id, wishlist.id)
        return WishlistRow(
            wishlist_id=wishlist.id,
            draft_id=wishlist.draft_id,
            participant_id=wishlist.participant_id,
            enabled=wishlist.enabled,
            players=rows,
        )

    async def set_enabled(
        self,
        draft_id: int,
        participant_id: int,
        enabled: bool,
    ) -> None:
        await self.session.execute(
            update(DraftWishlist)
            .where(
                DraftWishlist.draft_id == draft_id,
                DraftWishlist.participant_id == participant_id,
            )
            .values(enabled=enabled)
        )

    async def get_next_available_player(
        self,
        draft_id: int,
        participant_id: int,
    ) -> int | None:
        """Return the player_id of the highest-priority wishlist entry that
        is still pickable (player is_available, not yet drafted).

        Returns None if the participant has no enabled wishlist, has it
        empty, or every candidate has already been picked.
        """
        picked_subq = select(DraftPick.player_id).where(DraftPick.draft_id == draft_id)
        stmt = (
            select(DraftWishlistPlayer.player_id)
            .join(DraftWishlist, DraftWishlist.id == DraftWishlistPlayer.wishlist_id)
            .join(Player, Player.id == DraftWishlistPlayer.player_id)
            .where(
                DraftWishlist.draft_id == draft_id,
                DraftWishlist.participant_id == participant_id,
                DraftWishlist.enabled.is_(True),
                Player.is_available.is_(True),
                DraftWishlistPlayer.player_id.notin_(picked_subq),
            )
            .order_by(DraftWishlistPlayer.priority.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return row[0] if row else None

    async def list_for_admin(self, draft_id: int) -> list[AdminWishlistRow]:
        """Audit summary — counts only, no player_ids leave the DB.

        The admin endpoint must NOT expose the contents of a wishlist
        (that would defeat the privacy guarantee the participant expects
        when configuring it). The reported count is the number of
        entries STILL ELIGIBLE for the auto-pick engine, i.e. excluding
        players already drafted in this draft or flagged
        ``is_available = FALSE``. That matches the eligibility filter in
        :meth:`get_next_available_player` so the number the admin sees
        reflects what the engine would still consider.
        """
        picked_subq = select(DraftPick.player_id).where(DraftPick.draft_id == draft_id)
        eligible_subq = (
            select(
                DraftWishlistPlayer.wishlist_id.label("wid"),
                func.count(DraftWishlistPlayer.id).label("total"),
            )
            .join(Player, Player.id == DraftWishlistPlayer.player_id)
            .where(
                Player.is_available.is_(True),
                DraftWishlistPlayer.player_id.notin_(picked_subq),
            )
            .group_by(DraftWishlistPlayer.wishlist_id)
            .subquery()
        )
        wishlists_stmt = (
            select(
                DraftWishlist.id,
                DraftWishlist.participant_id,
                DraftWishlist.enabled,
                User.display_name,
                func.coalesce(eligible_subq.c.total, 0).label("total"),
            )
            .join(
                SeasonParticipant,
                SeasonParticipant.id == DraftWishlist.participant_id,
            )
            .join(User, User.id == SeasonParticipant.user_id)
            .outerjoin(eligible_subq, eligible_subq.c.wid == DraftWishlist.id)
            .where(DraftWishlist.draft_id == draft_id)
            .order_by(User.display_name.asc())
        )
        wl_rows = (await self.session.execute(wishlists_stmt)).all()
        return [
            AdminWishlistRow(
                wishlist_id=row.id,
                participant_id=row.participant_id,
                display_name=row.display_name,
                enabled=row.enabled,
                total=row.total,
            )
            for row in wl_rows
        ]

    async def _fetch_player_rows(
        self,
        draft_id: int,
        wishlist_id: int,
    ) -> list[WishlistPlayerRow]:
        picked_subq = select(DraftPick.player_id).where(DraftPick.draft_id == draft_id)
        stmt = (
            select(
                DraftWishlistPlayer.player_id,
                DraftWishlistPlayer.priority,
                Player.display_name,
                Player.position,
                Player.photo_path,
                Team.name.label("team_name"),
                DraftWishlistPlayer.player_id.in_(picked_subq).label("is_already_picked"),
            )
            .join(Player, Player.id == DraftWishlistPlayer.player_id)
            .outerjoin(Team, Player.team_id == Team.id)
            .where(DraftWishlistPlayer.wishlist_id == wishlist_id)
            .order_by(DraftWishlistPlayer.priority.asc())
        )
        result = await self.session.execute(stmt)
        return [
            WishlistPlayerRow(
                player_id=row.player_id,
                display_name=row.display_name,
                position=row.position,
                team_name=row.team_name,
                photo_path=row.photo_path,
                priority=row.priority,
                is_already_picked=bool(row.is_already_picked),
            )
            for row in result.all()
        ]

    async def validate_players_belong_to_season(
        self,
        season_id: int,
        player_ids: list[int],
    ) -> set[int]:
        """Return the subset of *player_ids* that are valid (in the season
        and is_available). The service uses this to reject the request
        when any id is missing or unavailable."""
        if not player_ids:
            return set()
        stmt = select(Player.id).where(
            Player.id.in_(player_ids),
            Player.season_id == season_id,
            Player.is_available.is_(True),
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result.all()}
