"""Compute the 🍔 Burger Ranking for a season.

For each participant we count the goals (open play + penalty) scored by a
player they OWN (players.owner_id == participant.id) on matchdays where
that player was NOT in their lineup_players. Own goals don't count.

Counting matchdays only (matchdays.counts = TRUE); cancelled / friendly
slots that don't score for the season-wide standings are excluded too.

Participants without any unburned goals still appear with total = 0 so
the UI can show the whole roster.
"""

from __future__ import annotations

from collections import OrderedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.burger_ranking.schemas import (
    BenchedPlayer,
    BenchEntry,
    BenchRankingResponse,
    BurgerEntry,
    BurgerGoal,
    BurgerRankingResponse,
)

_RANKING_SQL = text(
    """
    WITH lineup_pids AS (
        SELECT
            l.participant_id,
            l.matchday_id,
            lp.player_id
        FROM   lineups l
        JOIN   lineup_players lp ON lp.lineup_id = l.id
    )
    SELECT
        sp.id                            AS participant_id,
        u.display_name                   AS display_name,
        md.number                        AS matchday_number,
        p.id                             AS player_id,
        p.display_name                   AS player_name,
        t.name                           AS team_name,
        (ps.goals + ps.penalty_goals)    AS goals
    FROM       season_participants sp
    JOIN       users u          ON u.id = sp.user_id
    JOIN       players p        ON p.owner_id = sp.id
    JOIN       player_stats ps  ON ps.player_id = p.id
    JOIN       matchdays md     ON md.id = ps.matchday_id
    JOIN       teams t          ON t.id = p.team_id
    LEFT JOIN  lineup_pids lp
        ON lp.participant_id = sp.id
       AND lp.matchday_id    = md.id
       AND lp.player_id      = p.id
    WHERE      sp.season_id         = :season_id
      AND      md.counts             = TRUE
      AND      (ps.goals + ps.penalty_goals) > 0
      AND      lp.player_id IS NULL          -- not lineup'd this matchday
    ORDER BY   sp.id, md.number, p.display_name
    """
)


_PARTICIPANTS_SQL = text(
    """
    SELECT sp.id, u.display_name
    FROM   season_participants sp
    JOIN   users u ON u.id = sp.user_id
    WHERE  sp.season_id = :season_id
      AND  sp.is_active = TRUE
    ORDER BY u.display_name
    """
)


class BurgerRankingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_ranking(self, season_id: int) -> BurgerRankingResponse:
        # Pre-seed every active participant with an empty entry so the
        # UI shows everyone, even those who never had a goal slip past
        # the lineup.
        seed = await self.session.execute(_PARTICIPANTS_SQL, {"season_id": season_id})
        entries: OrderedDict[int, BurgerEntry] = OrderedDict()
        for row in seed.mappings():
            pid = int(row["id"])
            entries[pid] = BurgerEntry(
                participant_id=pid,
                display_name=row["display_name"],
                total=0,
                goals=[],
            )

        result = await self.session.execute(_RANKING_SQL, {"season_id": season_id})
        for row in result.mappings():
            pid = int(row["participant_id"])
            entry = entries.get(pid)
            if entry is None:
                # Participant must have been deactivated mid-season —
                # show them anyway so the totals add up.
                entry = BurgerEntry(
                    participant_id=pid,
                    display_name=row["display_name"],
                    total=0,
                    goals=[],
                )
                entries[pid] = entry
            goals_int = int(row["goals"])
            entry.total += goals_int
            entry.goals.append(
                BurgerGoal(
                    matchday_number=int(row["matchday_number"]),
                    player_id=int(row["player_id"]),
                    player_name=row["player_name"],
                    team_name=row["team_name"],
                    goals=goals_int,
                )
            )

        ranked = sorted(
            entries.values(),
            key=lambda e: (-e.total, e.display_name.lower()),
        )
        return BurgerRankingResponse(season_id=season_id, entries=ranked)


_BENCH_SQL = text(
    """
    SELECT
        sp.id                           AS participant_id,
        u.display_name                  AS display_name,
        md.number                       AS matchday_number,
        p.id                            AS player_id,
        p.display_name                  AS player_name,
        t.name                          AS team_name,
        COALESCE(ps.position, p.position, '') AS position
    FROM       lineups l
    JOIN       season_participants sp ON sp.id = l.participant_id
    JOIN       users u               ON u.id  = sp.user_id
    JOIN       matchdays md          ON md.id = l.matchday_id
    JOIN       lineup_players lp     ON lp.lineup_id = l.id
    JOIN       players p             ON p.id = lp.player_id
    JOIN       teams t               ON t.id = p.team_id
    LEFT JOIN  player_stats ps
        ON ps.player_id   = lp.player_id
       AND ps.matchday_id = l.matchday_id
    WHERE      sp.season_id   = :season_id
      AND      md.counts      = TRUE
      AND      COALESCE(ps.minutes_played, 0) = 0
    ORDER BY   sp.id, md.number, p.display_name
    """
)


class BenchRankingService:
    """Count players the manager lined up that played 0 minutes.

    Same matchday filter as the burger ranking (counts=TRUE only).
    Each (lineup, player) where minutes_played is 0 (or no stats row
    at all, meaning the player never appeared) counts as a banquillazo.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_ranking(self, season_id: int) -> BenchRankingResponse:
        seed = await self.session.execute(_PARTICIPANTS_SQL, {"season_id": season_id})
        entries: OrderedDict[int, BenchEntry] = OrderedDict()
        for row in seed.mappings():
            pid = int(row["id"])
            entries[pid] = BenchEntry(
                participant_id=pid,
                display_name=row["display_name"],
                total=0,
                players=[],
            )

        result = await self.session.execute(_BENCH_SQL, {"season_id": season_id})
        for row in result.mappings():
            pid = int(row["participant_id"])
            entry = entries.get(pid)
            if entry is None:
                entry = BenchEntry(
                    participant_id=pid,
                    display_name=row["display_name"],
                    total=0,
                    players=[],
                )
                entries[pid] = entry
            entry.total += 1
            entry.players.append(
                BenchedPlayer(
                    matchday_number=int(row["matchday_number"]),
                    player_id=int(row["player_id"]),
                    player_name=row["player_name"],
                    team_name=row["team_name"],
                    position=row["position"],
                )
            )

        ranked = sorted(
            entries.values(),
            key=lambda e: (-e.total, e.display_name.lower()),
        )
        return BenchRankingResponse(season_id=season_id, entries=ranked)
