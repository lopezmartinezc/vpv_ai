from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season, ValidFormation
from src.shared.models.team import Team


class LineupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_season(self, season_id: int) -> Season | None:
        return await self.session.get(Season, season_id)

    async def get_participant_for_user(
        self, season_id: int, user_id: int
    ) -> SeasonParticipant | None:
        stmt = select(SeasonParticipant).where(
            SeasonParticipant.season_id == season_id,
            SeasonParticipant.user_id == user_id,
            SeasonParticipant.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_matchday(
        self, season_id: int, number: int
    ) -> Matchday | None:
        stmt = select(Matchday).where(
            Matchday.season_id == season_id,
            Matchday.number == number,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_valid_formation(self, formation: str) -> ValidFormation | None:
        stmt = select(ValidFormation).where(ValidFormation.formation == formation)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_participant_player_ids(self, participant_id: int) -> set[int]:
        stmt = select(Player.id).where(
            Player.owner_id == participant_id,
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def get_lineup(
        self, participant_id: int, matchday_id: int
    ) -> Lineup | None:
        stmt = select(Lineup).where(
            Lineup.participant_id == participant_id,
            Lineup.matchday_id == matchday_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_previous_lineup(
        self, participant_id: int, season_id: int, matchday_number: int
    ) -> Lineup | None:
        """Get the lineup from the previous matchday (number - 1)."""
        if matchday_number <= 1:
            return None
        subq = select(Matchday.id).where(
            Matchday.season_id == season_id,
            Matchday.number == matchday_number - 1,
        ).scalar_subquery()
        stmt = select(Lineup).where(
            Lineup.participant_id == participant_id,
            Lineup.matchday_id == subq,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_previous_lineup_players(self, lineup_id: int) -> list[LineupPlayer]:
        stmt = (
            select(LineupPlayer)
            .where(LineupPlayer.lineup_id == lineup_id)
            .order_by(LineupPlayer.display_order)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_lineup(
        self,
        participant_id: int,
        matchday_id: int,
        formation: str,
        players: list[dict],
    ) -> Lineup:
        """Create or update a lineup. Always marks confirmed=True, resets telegram_sent."""
        existing = await self.get_lineup(participant_id, matchday_id)

        if existing:
            existing.formation = formation
            existing.confirmed = True
            existing.confirmed_at = datetime.now(timezone.utc)
            existing.telegram_sent = False
            existing.telegram_sent_at = None
            existing.image_path = None
            lineup = existing
            # Delete old lineup players
            await self.session.execute(
                delete(LineupPlayer).where(LineupPlayer.lineup_id == lineup.id)
            )
        else:
            lineup = Lineup(
                participant_id=participant_id,
                matchday_id=matchday_id,
                formation=formation,
                confirmed=True,
                confirmed_at=datetime.now(timezone.utc),
            )
            self.session.add(lineup)
            await self.session.flush()  # get lineup.id

        # Create new lineup players
        for i, p in enumerate(players, start=1):
            lp = LineupPlayer(
                lineup_id=lineup.id,
                player_id=p["player_id"],
                position_slot=p["position_slot"],
                display_order=i,
            )
            self.session.add(lp)

        await self.session.flush()
        return lineup

    async def copy_previous_lineup(
        self,
        from_lineup_id: int,
        from_formation: str,
        participant_id: int,
        to_matchday_id: int,
    ) -> Lineup:
        """Copy a lineup from a previous matchday to a new one."""
        prev_players = await self.get_previous_lineup_players(from_lineup_id)

        lineup = Lineup(
            participant_id=participant_id,
            matchday_id=to_matchday_id,
            formation=from_formation,
            confirmed=True,
            confirmed_at=datetime.now(timezone.utc),
        )
        self.session.add(lineup)
        await self.session.flush()

        for pp in prev_players:
            lp = LineupPlayer(
                lineup_id=lineup.id,
                player_id=pp.player_id,
                position_slot=pp.position_slot,
                display_order=pp.display_order,
            )
            self.session.add(lp)

        await self.session.flush()
        return lineup

    async def get_participants_without_lineup(
        self, season_id: int, matchday_id: int
    ) -> list[SeasonParticipant]:
        """Active participants that have NOT submitted a lineup for this matchday."""
        existing_ids = (
            select(Lineup.participant_id)
            .where(Lineup.matchday_id == matchday_id)
            .scalar_subquery()
        )
        stmt = select(SeasonParticipant).where(
            SeasonParticipant.season_id == season_id,
            SeasonParticipant.is_active.is_(True),
            SeasonParticipant.id.notin_(existing_ids),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_lineup_for_image(self, lineup_id: int) -> dict | None:
        """Get all data needed to generate the lineup image."""
        from src.shared.models.user import User

        stmt = (
            select(
                Lineup.id,
                Lineup.formation,
                Matchday.number.label("matchday_number"),
                User.display_name.label("user_display_name"),
            )
            .join(Matchday, Lineup.matchday_id == Matchday.id)
            .join(SeasonParticipant, Lineup.participant_id == SeasonParticipant.id)
            .join(User, SeasonParticipant.user_id == User.id)
            .where(Lineup.id == lineup_id)
        )
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None

        # Get players
        player_stmt = (
            select(
                LineupPlayer.position_slot,
                LineupPlayer.display_order,
                Player.display_name.label("player_name"),
                Player.photo_path,
            )
            .join(Player, LineupPlayer.player_id == Player.id)
            .where(LineupPlayer.lineup_id == lineup_id)
            .order_by(LineupPlayer.display_order)
        )
        player_result = await self.session.execute(player_stmt)
        players = [dict(r._mapping) for r in player_result.all()]

        return {
            "lineup_id": row.id,
            "formation": row.formation,
            "matchday_number": row.matchday_number,
            "user_display_name": row.user_display_name,
            "players": players,
        }

    async def mark_telegram_sent(
        self, lineup_id: int, image_path: str | None = None
    ) -> None:
        lineup = await self.session.get(Lineup, lineup_id)
        if lineup:
            lineup.telegram_sent = True
            lineup.telegram_sent_at = datetime.now(timezone.utc)
            if image_path:
                lineup.image_path = image_path

    async def get_lineup_players_response(self, lineup_id: int) -> list[dict]:
        """Get lineup players with player names for response."""
        stmt = (
            select(
                LineupPlayer.player_id,
                Player.display_name.label("player_name"),
                LineupPlayer.position_slot,
                LineupPlayer.display_order,
                Player.photo_path,
            )
            .join(Player, LineupPlayer.player_id == Player.id)
            .where(LineupPlayer.lineup_id == lineup_id)
            .order_by(LineupPlayer.display_order)
        )
        result = await self.session.execute(stmt)
        return [dict(r._mapping) for r in result.all()]

    async def get_squad_players(
        self, season_id: int, participant_id: int
    ) -> list[dict]:
        """Get all players in a participant's squad with season points."""
        season_pts = func.coalesce(
            func.sum(
                case(
                    (Matchday.counts.is_(True), PlayerStat.pts_total),
                    else_=0,
                ),
            ),
            0,
        ).label("season_points")

        # Position ordering: POR=1, DEF=2, MED=3, DEL=4
        pos_order = case(
            (Player.position == "POR", 1),
            (Player.position == "DEF", 2),
            (Player.position == "MED", 3),
            (Player.position == "DEL", 4),
            else_=5,
        )

        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.photo_path,
                Player.position,
                Team.name.label("team_name"),
                season_pts,
            )
            .join(Team, Player.team_id == Team.id)
            .outerjoin(PlayerStat, PlayerStat.player_id == Player.id)
            .outerjoin(
                Matchday,
                and_(
                    PlayerStat.matchday_id == Matchday.id,
                    Matchday.season_id == season_id,
                ),
            )
            .where(
                Player.season_id == season_id,
                Player.owner_id == participant_id,
            )
            .group_by(
                Player.id, Player.display_name, Player.photo_path,
                Player.position, Team.name,
            )
            .order_by(pos_order.asc(), season_pts.desc())
        )

        result = await self.session.execute(stmt)
        return [dict(r._mapping) for r in result.all()]
