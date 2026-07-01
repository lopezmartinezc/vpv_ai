"""Survivors ranking — tournaments only.

For each participant, count how many of their owned players are still ALIVE
(their national team is still in the bracket) vs ELIMINATED. Reuses the
tournament team-status logic (group qualifiers + knockout losers, penalty
losers included) and the static ``players.owner_id`` ownership used by
tournament seasons.
"""

from __future__ import annotations

from collections import OrderedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.burger_ranking.schemas import (
    SurvivorEntry,
    SurvivorPlayer,
    SurvivorsResponse,
)
from src.features.tournaments.service import TournamentService

_SEASON_KIND_SQL = text("SELECT kind FROM seasons WHERE id = :season_id")

_SQUADS_SQL = text(
    """
    SELECT sp.id            AS participant_id,
           u.display_name   AS display_name,
           p.id             AS player_id,
           p.display_name   AS player_name,
           COALESCE(p.position, '') AS position,
           p.team_id        AS team_id,
           t.name           AS team_name
    FROM       season_participants sp
    JOIN       users u  ON u.id = sp.user_id
    LEFT JOIN  players p ON p.owner_id = sp.id AND p.season_id = :season_id
    LEFT JOIN  teams t   ON t.id = p.team_id
    WHERE      sp.season_id = :season_id
      AND      sp.is_active = TRUE
    ORDER BY   u.display_name
    """
)

_POS_ORDER = {"POR": 0, "DEF": 1, "MED": 2, "DEL": 3}


class SurvivorsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_ranking(self, season_id: int) -> SurvivorsResponse | None:
        """Return the survivors ranking, or ``None`` for non-tournament seasons."""
        kind = (await self.session.execute(_SEASON_KIND_SQL, {"season_id": season_id})).scalar()
        if kind != "tournament":
            return None

        status = await TournamentService(self.session).get_team_status(season_id)
        alive_teams = set(status.alive_team_ids)

        entries: OrderedDict[int, SurvivorEntry] = OrderedDict()
        rows = await self.session.execute(_SQUADS_SQL, {"season_id": season_id})
        for row in rows.mappings():
            pid = int(row["participant_id"])
            entry = entries.get(pid)
            if entry is None:
                entry = SurvivorEntry(
                    participant_id=pid,
                    display_name=row["display_name"],
                    alive_count=0,
                    eliminated_count=0,
                    total=0,
                    players=[],
                )
                entries[pid] = entry
            if row["player_id"] is None:
                continue  # participant with no players — keep the empty row
            alive = row["team_id"] in alive_teams
            entry.players.append(
                SurvivorPlayer(
                    player_id=int(row["player_id"]),
                    player_name=row["player_name"],
                    team_name=row["team_name"] or "",
                    position=row["position"],
                    alive=alive,
                )
            )
            entry.total += 1
            if alive:
                entry.alive_count += 1
            else:
                entry.eliminated_count += 1

        ordered = sorted(
            entries.values(),
            key=lambda e: (-e.alive_count, e.eliminated_count, e.display_name),
        )
        for e in ordered:
            # Alive first, then by position, then name.
            e.players.sort(
                key=lambda p: (not p.alive, _POS_ORDER.get(p.position, 9), p.player_name)
            )

        return SurvivorsResponse(
            season_id=season_id,
            group_stage_done=status.group_stage_done,
            entries=ordered,
        )
