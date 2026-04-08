from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, case, delete, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_ownership_log import PlayerOwnershipLog
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

    async def get_matchday(self, season_id: int, number: int) -> Matchday | None:
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

    async def get_lineup(self, participant_id: int, matchday_id: int) -> Lineup | None:
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
        subq = (
            select(Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.number == matchday_number - 1,
            )
            .scalar_subquery()
        )
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
            existing.confirmed_at = datetime.now(UTC)
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
                confirmed_at=datetime.now(UTC),
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
            confirmed_at=datetime.now(UTC),
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

    async def mark_telegram_sent(self, lineup_id: int, image_path: str | None = None) -> None:
        lineup = await self.session.get(Lineup, lineup_id)
        if lineup:
            lineup.telegram_sent = True
            lineup.telegram_sent_at = datetime.now(UTC)
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

    async def get_squad_players(self, season_id: int, participant_id: int) -> list[dict]:
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
                Player.id,
                Player.display_name,
                Player.photo_path,
                Player.position,
                Team.name,
            )
            .order_by(pos_order.asc(), season_pts.desc())
        )

        result = await self.session.execute(stmt)
        return [dict(r._mapping) for r in result.all()]

    async def get_squad_recent_form(
        self, season_id: int, player_ids: list[int], n: int = 5
    ) -> dict[int, dict]:
        """Get last N matchday stats per player for form display.

        Includes matchdays where the player did NOT play (played=False),
        so the frontend can show disabled slots in the form indicator.

        Returns dict[player_id] with matches list + aggregate stats.
        """
        if not player_ids:
            return {}

        # 1. Get last N completed counting matchdays for this season
        recent_mds_stmt = (
            select(Matchday.id, Matchday.number)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                Matchday.stats_ok.is_(True),
            )
            .order_by(Matchday.number.desc())
            .limit(n)
        )
        recent_mds_result = await self.session.execute(recent_mds_stmt)
        recent_mds = list(recent_mds_result.all())
        if not recent_mds:
            return {}

        # Ordered oldest → newest
        recent_mds.reverse()
        md_ids = [md.id for md in recent_mds]
        md_numbers = [md.number for md in recent_mds]

        # 2. Fetch player stats for these matchdays (including non-played via LEFT JOIN)
        is_home = case(
            (Player.team_id == Match.home_team_id, True),
            else_=False,
        ).label("is_home")

        stmt = (
            select(
                PlayerStat.player_id,
                PlayerStat.played,
                PlayerStat.result,
                PlayerStat.pts_total,
                PlayerStat.pts_clean_sheet,
                PlayerStat.goals,
                PlayerStat.assists,
                PlayerStat.penalty_goals,
                PlayerStat.yellow_card,
                Matchday.number.label("md_number"),
                is_home,
            )
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .join(Player, PlayerStat.player_id == Player.id)
            .outerjoin(Match, PlayerStat.match_id == Match.id)
            .where(
                PlayerStat.player_id.in_(player_ids),
                PlayerStat.matchday_id.in_(md_ids),
            )
            .order_by(PlayerStat.player_id, Matchday.number)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        # Index stats by (player_id, md_number)
        stats_index: dict[tuple[int, int], Any] = {}
        for row in rows:
            stats_index[(row.player_id, row.md_number)] = row

        # 3. Build form data — include empty slots for matchdays without stats
        form_data: dict[int, dict] = {}
        for pid in player_ids:
            matches: list[dict] = []
            clean_sheets = 0
            goals = 0
            assists = 0
            penalty_goals = 0
            yellow_cards = 0

            for md_num in md_numbers:
                stat = stats_index.get((pid, md_num))
                if stat is None or not stat.played:
                    matches.append(
                        {
                            "played": False,
                            "result": 0,
                            "is_home": False,
                            "points": 0,
                        }
                    )
                else:
                    matches.append(
                        {
                            "played": True,
                            "result": stat.result or 0,
                            "is_home": bool(stat.is_home),
                            "points": stat.pts_total or 0,
                        }
                    )
                    if (stat.pts_clean_sheet or 0) > 0:
                        clean_sheets += 1
                    goals += stat.goals or 0
                    assists += stat.assists or 0
                    penalty_goals += stat.penalty_goals or 0
                    if stat.yellow_card:
                        yellow_cards += 1

            form_data[pid] = {
                "matches": matches,
                "clean_sheets": clean_sheets,
                "goals": goals,
                "assists": assists,
                "penalty_goals": penalty_goals,
                "yellow_cards": yellow_cards,
            }

        return form_data

    async def get_participant_lineups(self, participant_id: int, season_id: int) -> list[dict]:
        """Get all lineups for a participant in a season, with players and points.

        Returns list of dicts with lineup info + nested player list,
        ordered by matchday number descending.
        """
        # 1. Get all lineups for this participant in this season
        stmt = (
            select(
                Lineup.id.label("lineup_id"),
                Lineup.formation,
                Lineup.total_points,
                Lineup.confirmed_at,
                Matchday.number.label("matchday_number"),
            )
            .join(Matchday, Lineup.matchday_id == Matchday.id)
            .where(
                Lineup.participant_id == participant_id,
                Matchday.season_id == season_id,
            )
            .order_by(Matchday.number.desc())
        )
        result = await self.session.execute(stmt)
        lineup_rows = result.all()

        if not lineup_rows:
            return []

        # 2. Get all players for these lineups in one query
        lineup_ids = [r.lineup_id for r in lineup_rows]
        players_stmt = (
            select(
                LineupPlayer.lineup_id,
                LineupPlayer.player_id,
                Player.display_name.label("player_name"),
                LineupPlayer.position_slot,
                LineupPlayer.display_order,
                Player.photo_path,
                LineupPlayer.points,
            )
            .join(Player, LineupPlayer.player_id == Player.id)
            .where(LineupPlayer.lineup_id.in_(lineup_ids))
            .order_by(LineupPlayer.lineup_id, LineupPlayer.display_order)
        )
        players_result = await self.session.execute(players_stmt)
        all_players = players_result.all()

        # Group players by lineup_id
        players_by_lineup: dict[int, list[dict]] = {}
        for p in all_players:
            players_by_lineup.setdefault(p.lineup_id, []).append(
                {
                    "player_id": p.player_id,
                    "player_name": p.player_name,
                    "position_slot": p.position_slot,
                    "display_order": p.display_order,
                    "photo_path": p.photo_path,
                    "points": p.points or 0,
                }
            )

        # 3. Build result
        return [
            {
                "matchday_number": r.matchday_number,
                "formation": r.formation,
                "total_points": r.total_points or 0,
                "confirmed_at": r.confirmed_at,
                "players": players_by_lineup.get(r.lineup_id, []),
            }
            for r in lineup_rows
        ]

    async def get_accuracy_data(self, participant_id: int, season_id: int) -> list[dict]:
        """Get data needed to calculate lineup accuracy per matchday.

        For each completed counting matchday where the participant has a lineup:
        - The lineup (formation, total_points, lined-up player IDs)
        - All squad players' stats (using ownership log for correct historical ownership)

        Returns list of dicts ordered by matchday number DESC.
        """
        # 1. Get all completed counting matchdays
        md_stmt = (
            select(Matchday.id, Matchday.number)
            .where(
                Matchday.season_id == season_id,
                Matchday.counts.is_(True),
                Matchday.stats_ok.is_(True),
            )
            .order_by(Matchday.number.desc())
        )
        md_result = await self.session.execute(md_stmt)
        matchdays = md_result.all()
        if not matchdays:
            return []

        md_ids = [m.id for m in matchdays]
        md_id_to_number = {m.id: m.number for m in matchdays}

        # 2. Get all lineups for this participant in these matchdays
        lineup_stmt = select(
            Lineup.id.label("lineup_id"),
            Lineup.matchday_id,
            Lineup.formation,
            Lineup.total_points,
        ).where(
            Lineup.participant_id == participant_id,
            Lineup.matchday_id.in_(md_ids),
        )
        lineup_result = await self.session.execute(lineup_stmt)
        lineups = {r.matchday_id: r for r in lineup_result.all()}

        if not lineups:
            return []

        # 3. Get lined-up player IDs per lineup
        lineup_ids = [r.lineup_id for r in lineups.values()]
        lp_stmt = select(LineupPlayer.lineup_id, LineupPlayer.player_id).where(
            LineupPlayer.lineup_id.in_(lineup_ids)
        )
        lp_result = await self.session.execute(lp_stmt)
        lined_up_by_lineup: dict[int, set[int]] = {}
        for r in lp_result.all():
            lined_up_by_lineup.setdefault(r.lineup_id, set()).add(r.player_id)

        # 4. For each matchday, get all owned players' stats
        results: list[dict] = []
        for md in matchdays:
            lineup = lineups.get(md.id)
            if lineup is None:
                continue

            md_number = md_id_to_number[md.id]

            # Ownership subquery for this matchday
            row_num = (
                func.row_number()
                .over(
                    partition_by=PlayerOwnershipLog.player_id,
                    order_by=PlayerOwnershipLog.from_matchday.desc(),
                )
                .label("rn")
            )
            ownership_inner = (
                select(
                    PlayerOwnershipLog.player_id,
                    PlayerOwnershipLog.participant_id,
                    row_num,
                )
                .where(
                    PlayerOwnershipLog.season_id == season_id,
                    PlayerOwnershipLog.from_matchday <= md_number,
                )
                .subquery()
            )
            ownership = (
                select(ownership_inner.c.player_id, ownership_inner.c.participant_id)
                .where(ownership_inner.c.rn == 1)
                .subquery()
            )

            # Get stats for owned players, respecting match.counts
            stats_stmt = (
                select(
                    PlayerStat.player_id,
                    PlayerStat.position,
                    PlayerStat.pts_total,
                    PlayerStat.played,
                    Player.display_name,
                )
                .join(Player, PlayerStat.player_id == Player.id)
                .join(ownership, ownership.c.player_id == PlayerStat.player_id)
                .outerjoin(Match, PlayerStat.match_id == Match.id)
                .where(
                    ownership.c.participant_id == participant_id,
                    PlayerStat.matchday_id == md.id,
                    func.coalesce(Match.counts, literal(True)).is_(True),
                )
            )
            stats_result = await self.session.execute(stats_stmt)
            squad_stats = [
                {
                    "player_id": r.player_id,
                    "name": r.display_name,
                    "position": r.position,
                    "pts": r.pts_total if r.played else 0,
                    "played": r.played,
                }
                for r in stats_result.all()
            ]

            lined_up_ids = lined_up_by_lineup.get(lineup.lineup_id, set())

            results.append(
                {
                    "matchday_number": md_number,
                    "formation": lineup.formation,
                    "actual_points": lineup.total_points or 0,
                    "squad_stats": squad_stats,
                    "lined_up_ids": lined_up_ids,
                }
            )

        return results

    async def get_valid_formations(self) -> list[ValidFormation]:
        stmt = select(ValidFormation)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Admin lineup editing
    # ------------------------------------------------------------------

    async def get_all_lineups_for_matchday(self, season_id: int, matchday_id: int) -> list[dict]:
        """Get all participant lineups for a matchday (admin view)."""
        from src.shared.models.user import User

        # All active participants
        part_stmt = (
            select(
                SeasonParticipant.id.label("participant_id"),
                User.display_name,
            )
            .join(User, SeasonParticipant.user_id == User.id)
            .where(
                SeasonParticipant.season_id == season_id,
                SeasonParticipant.is_active.is_(True),
            )
            .order_by(User.display_name)
        )
        part_result = await self.session.execute(part_stmt)
        participants = part_result.all()

        # Lineups for this matchday
        lineup_stmt = select(Lineup).where(Lineup.matchday_id == matchday_id)
        lineup_result = await self.session.execute(lineup_stmt)
        lineups_by_part: dict[int, Lineup] = {
            lu.participant_id: lu for lu in lineup_result.scalars().all()
        }

        # All lineup players in one query
        lineup_ids = [lu.id for lu in lineups_by_part.values()]
        players_by_lineup: dict[int, list[dict]] = {}
        if lineup_ids:
            lp_stmt = (
                select(
                    LineupPlayer.lineup_id,
                    LineupPlayer.player_id,
                    Player.display_name.label("display_name"),
                    LineupPlayer.position_slot,
                    LineupPlayer.display_order,
                    LineupPlayer.points,
                    Player.photo_path,
                )
                .join(Player, LineupPlayer.player_id == Player.id)
                .where(LineupPlayer.lineup_id.in_(lineup_ids))
                .order_by(LineupPlayer.lineup_id, LineupPlayer.display_order)
            )
            lp_result = await self.session.execute(lp_stmt)
            for r in lp_result.all():
                players_by_lineup.setdefault(r.lineup_id, []).append(
                    {
                        "player_id": r.player_id,
                        "display_name": r.display_name,
                        "position_slot": r.position_slot,
                        "display_order": r.display_order,
                        "points": r.points or 0,
                        "photo_path": r.photo_path,
                    }
                )

        result_list = []
        for p in participants:
            lu = lineups_by_part.get(p.participant_id)
            result_list.append(
                {
                    "participant_id": p.participant_id,
                    "display_name": p.display_name,
                    "has_lineup": lu is not None,
                    "formation": lu.formation if lu else None,
                    "total_points": lu.total_points if lu else 0,
                    "confirmed_at": lu.confirmed_at if lu else None,
                    "players": players_by_lineup.get(lu.id, []) if lu else [],
                }
            )
        return result_list

    async def get_squad_for_matchday(
        self, season_id: int, participant_id: int, matchday_id: int
    ) -> list[dict]:
        """Get participant squad with points for a specific matchday."""
        pos_order = case(
            (Player.position == "POR", 1),
            (Player.position == "DEF", 2),
            (Player.position == "MED", 3),
            (Player.position == "DEL", 4),
            else_=5,
        )

        # Points from player_stats for this matchday (respecting match.counts)
        pts_sub = (
            select(func.coalesce(PlayerStat.pts_total, 0))
            .outerjoin(Match, PlayerStat.match_id == Match.id)
            .where(
                PlayerStat.player_id == Player.id,
                PlayerStat.matchday_id == matchday_id,
                func.coalesce(Match.counts, literal(True)).is_(True),
            )
            .correlate(Player)
            .scalar_subquery()
        )

        stmt = (
            select(
                Player.id.label("player_id"),
                Player.display_name,
                Player.position,
                Team.name.label("team_name"),
                Player.photo_path,
                pts_sub.label("points_this_matchday"),
            )
            .join(Team, Player.team_id == Team.id)
            .where(
                Player.season_id == season_id,
                Player.owner_id == participant_id,
            )
            .order_by(pos_order.asc(), Player.display_name)
        )
        result = await self.session.execute(stmt)
        return [dict(r._mapping) for r in result.all()]
