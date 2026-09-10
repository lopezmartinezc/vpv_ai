"""Fixture difficulty — how hard a player's next opponents are, by position.

Measured over the 8 real seasons of the league, points lost by facing the
hardest instead of the easiest opponent:

===  ==========================  ============================
Pos  by the opponent's ATTACK    by the opponent's DEFENCE
===  ==========================  ============================
POR  2.58                        1.62
DEF  1.55                        1.40
MED  1.16                        1.57
DEL  1.43                        2.04
===  ==========================  ============================

A keeper wants an opponent who cannot score; a forward wants one who cannot
defend. Collapsing that into a single "hard fixture" number would average the
two into something wrong for everybody, so difficulty is always asked for a
position.

The same numbers drive two things: the weekly lineup (which of my players face
a soft opponent this matchday) and the draft assistant's calendar questions.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# League averages, from the same 8 seasons. Used as the prior for a promoted
# side with no top-flight history.
LEAGUE_ATTACK = 1.19
LEAGUE_DEFENCE = 1.19

# Matchdays of the current season needed before it outweighs the history.
# Mirrors the shrinkage the draft model already uses for thin samples.
SHRINKAGE_K = 6

# Thresholds are the tiers the effect was measured on, not round numbers.
HARD_ATTACK = 1.7  # opponent scores this much -> hard for POR/DEF
EASY_ATTACK = 1.2
EASY_DEFENCE = 1.5  # opponent concedes this much -> easy for MED/DEL
HARD_DEFENCE = 1.1

#: Which side of the opponent decides difficulty for each position.
GRADED_ON: dict[str, str] = {
    "POR": "attack",
    "DEF": "attack",
    "MED": "defence",
    "DEL": "defence",
}


@dataclass(frozen=True)
class TeamStrength:
    team_id: int
    name: str
    attack: float  # goals scored per match
    defence: float  # goals conceded per match


@dataclass(frozen=True)
class Fixture:
    matchday: int
    team_id: int
    team_name: str
    opponent_id: int
    opponent_name: str
    home: bool
    opponent_attack: float
    opponent_defence: float


def difficulty(position: str, fixture: Fixture) -> str:
    """``facil`` | ``media`` | ``dificil`` for this position against this rival."""
    graded_on = GRADED_ON.get(position.upper())
    if graded_on is None:
        return "media"
    if graded_on == "attack":
        if fixture.opponent_attack >= HARD_ATTACK:
            return "dificil"
        if fixture.opponent_attack < EASY_ATTACK:
            return "facil"
        return "media"
    # Forwards and midfielders: a leaky opponent is the soft one.
    if fixture.opponent_defence >= EASY_DEFENCE:
        return "facil"
    if fixture.opponent_defence < HARD_DEFENCE:
        return "dificil"
    return "media"


def blend_strength(
    history: TeamStrength | None,
    current: TeamStrength | None,
    played: int,
    team_id: int = 0,
    name: str = "",
) -> TeamStrength:
    """Weigh this season against the previous ones by how much of it has happened.

    Four matchdays is noise and thirty is the truth, so the current season earns
    its weight as it accumulates: ``played / (played + K)``. A side with no
    history leans on the current season alone; one with neither — a promoted
    team before a ball is kicked — takes the league average rather than a zero
    that would read as an impenetrable defence.
    """
    if history is None and current is None:
        return TeamStrength(team_id, name, LEAGUE_ATTACK, LEAGUE_DEFENCE)
    if history is None:
        return current  # type: ignore[return-value]
    if current is None or played <= 0:
        return history

    w = played / (played + SHRINKAGE_K)
    return TeamStrength(
        team_id=history.team_id or current.team_id,
        name=history.name or current.name,
        attack=history.attack * (1 - w) + current.attack * w,
        defence=history.defence * (1 - w) + current.defence * w,
    )


class FixtureStrengthService:
    """Team strength and upcoming fixtures for a season."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def team_strength(self, season_id: int) -> dict[int, TeamStrength]:
        """Attack and defence per team, current season blended with history.

        History comes from the same clubs in prior seasons — joined by team
        NAME, because ``teams`` rows are per-season and the ids differ.
        """
        rows = await self.session.execute(
            text("""
                WITH actual AS (
                    SELECT t.id AS team_id, t.name,
                           AVG(m.gf) AS attack, AVG(m.ga) AS defence,
                           COUNT(*) AS played
                    FROM teams t
                    JOIN LATERAL (
                        SELECT CASE WHEN mm.home_team_id = t.id
                                    THEN mm.home_score ELSE mm.away_score END AS gf,
                               CASE WHEN mm.home_team_id = t.id
                                    THEN mm.away_score ELSE mm.home_score END AS ga
                        FROM matches mm
                        JOIN matchdays md ON md.id = mm.matchday_id
                        WHERE md.season_id = :sid
                          AND mm.home_score IS NOT NULL
                          AND t.id IN (mm.home_team_id, mm.away_team_id)
                    ) m ON TRUE
                    WHERE t.season_id = :sid
                    GROUP BY t.id, t.name
                ),
                histo AS (
                    SELECT t.name,
                           AVG(CASE WHEN mm.home_team_id = t.id
                                    THEN mm.home_score ELSE mm.away_score END) AS attack,
                           AVG(CASE WHEN mm.home_team_id = t.id
                                    THEN mm.away_score ELSE mm.home_score END) AS defence
                    FROM teams t
                    JOIN matches mm ON t.id IN (mm.home_team_id, mm.away_team_id)
                    JOIN matchdays md ON md.id = mm.matchday_id AND md.season_id = t.season_id
                    WHERE t.season_id < :sid AND mm.home_score IS NOT NULL
                    GROUP BY t.name
                )
                SELECT t.id AS team_id, t.name,
                       a.attack AS cur_attack, a.defence AS cur_defence,
                       COALESCE(a.played, 0) AS played,
                       h.attack AS hist_attack, h.defence AS hist_defence
                FROM teams t
                LEFT JOIN actual a ON a.team_id = t.id
                LEFT JOIN histo h ON h.name = t.name
                WHERE t.season_id = :sid
            """),
            {"sid": season_id},
        )

        out: dict[int, TeamStrength] = {}
        for r in rows:
            history = (
                TeamStrength(r.team_id, r.name, float(r.hist_attack), float(r.hist_defence))
                if r.hist_attack is not None
                else None
            )
            current = (
                TeamStrength(r.team_id, r.name, float(r.cur_attack), float(r.cur_defence))
                if r.cur_attack is not None
                else None
            )
            out[r.team_id] = blend_strength(
                history, current, int(r.played), team_id=r.team_id, name=r.name
            )
        return out

    async def fixtures(
        self,
        season_id: int,
        from_matchday: int = 1,
        count: int = 8,
        team_id: int | None = None,
    ) -> list[Fixture]:
        """Upcoming fixtures with the opponent's strength attached."""
        strength = await self.team_strength(season_id)
        rows = await self.session.execute(
            text("""
                SELECT md.number AS matchday, m.home_team_id, m.away_team_id,
                       ht.name AS home_name, at.name AS away_name
                FROM matches m
                JOIN matchdays md ON md.id = m.matchday_id AND md.season_id = :sid
                JOIN teams ht ON ht.id = m.home_team_id
                JOIN teams at ON at.id = m.away_team_id
                WHERE md.number >= :desde AND md.number < :hasta
                ORDER BY md.number
            """),
            {"sid": season_id, "desde": from_matchday, "hasta": from_matchday + count},
        )

        def _s(tid: int, name: str) -> TeamStrength:
            return strength.get(tid, TeamStrength(tid, name, LEAGUE_ATTACK, LEAGUE_DEFENCE))

        out: list[Fixture] = []
        for r in rows:
            home = _s(r.home_team_id, r.home_name)
            away = _s(r.away_team_id, r.away_name)
            pairs = (
                (r.home_team_id, r.home_name, r.away_team_id, r.away_name, True, away),
                (r.away_team_id, r.away_name, r.home_team_id, r.home_name, False, home),
            )
            for tid, tname, oid, oname, is_home, rival in pairs:
                if team_id is not None and tid != team_id:
                    continue
                out.append(
                    Fixture(
                        matchday=r.matchday,
                        team_id=tid,
                        team_name=tname,
                        opponent_id=oid,
                        opponent_name=oname,
                        home=is_home,
                        opponent_attack=round(rival.attack, 2),
                        opponent_defence=round(rival.defence, 2),
                    )
                )
        return out
