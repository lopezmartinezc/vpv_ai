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
