"""Reads for the lineup chat that no other feature already offers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.competition_matchup import CompetitionMatchup
from src.shared.models.matchday import Matchday
from src.shared.models.player import Player
from src.shared.models.player_availability import PlayerAvailability, TeamNews
from src.shared.models.season import ScoringRule, Season
from src.shared.models.team import Team


@dataclass(frozen=True)
class AvailabilityRow:
    reading: PlayerAvailability
    player_name: str | None
    team_name: str


@dataclass(frozen=True)
class NewsRow:
    item: TeamNews
    team_name: str


@dataclass(frozen=True)
class NamedPlayer:
    id: int
    name: str
    team_name: str
    position: str


@dataclass(frozen=True)
class HistoryRow:
    matchday: int
    played: bool
    minutes: int | None
    points: int
    marca: str | None
    as_picas: str | None
    goals: int
    assists: int
    yellow: bool
    red: bool


@dataclass(frozen=True)
class CalendarRow:
    played_at: datetime | None
    counts: bool
    home: str
    away: str


class LineupAssistantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def availability(self, season_id: int, matchday: int) -> list[AvailabilityRow]:
        result = await self.session.execute(
            select(PlayerAvailability, Player.display_name, Team.name)
            .join(Team, Team.id == PlayerAvailability.team_id)
            .outerjoin(Player, Player.id == PlayerAvailability.player_id)
            .where(
                PlayerAvailability.season_id == season_id,
                PlayerAvailability.matchday_number == matchday,
            )
            .order_by(Team.name, PlayerAvailability.raw_name, PlayerAvailability.source)
        )
        return [AvailabilityRow(reading, name, team) for reading, name, team in result.tuples()]

    async def news(self, season_id: int, limit: int = 400) -> list[NewsRow]:
        result = await self.session.execute(
            select(TeamNews, Team.name)
            .join(Team, Team.id == TeamNews.team_id)
            .where(TeamNews.season_id == season_id)
            .order_by(TeamNews.published_at.desc().nulls_last(), TeamNews.id.desc())
            .limit(limit)
        )
        return [NewsRow(item, team) for item, team in result.tuples()]

    async def players(self, season_id: int) -> list[NamedPlayer]:
        result = await self.session.execute(
            select(Player.id, Player.display_name, Team.name, Player.position)
            .join(Team, Team.id == Player.team_id)
            .where(Player.season_id == season_id)
        )
        return [NamedPlayer(*row) for row in result.tuples()]

    async def history(self, player_id: int, limit: int) -> list[HistoryRow]:
        """The player's last matchdays, newest first. Players are per season,
        so the id already fixes the season."""
        result = await self.session.execute(
            text("""
                SELECT md.number, ps.played, ps.minutes_played, ps.pts_total,
                       ps.marca_rating, ps.as_picas, ps.goals, ps.assists,
                       ps.yellow_card, (ps.red_card OR ps.double_yellow) AS red
                FROM player_stats ps
                JOIN matchdays md ON md.id = ps.matchday_id
                WHERE ps.player_id = :pid
                ORDER BY md.number DESC
                LIMIT :n
            """),
            {"pid": player_id, "n": limit},
        )
        return [
            HistoryRow(
                matchday=r[0],
                played=bool(r[1]),
                minutes=r[2],
                points=int(r[3] or 0),
                marca=r[4],
                as_picas=r[5],
                goals=int(r[6] or 0),
                assists=int(r[7] or 0),
                yellow=bool(r[8]),
                red=bool(r[9]),
            )
            for r in result
        ]

    async def season(self, season_id: int) -> Season | None:
        return await self.session.get(Season, season_id)

    async def matchday(self, season_id: int, number: int) -> Matchday | None:
        result = await self.session.execute(
            select(Matchday).where(Matchday.season_id == season_id, Matchday.number == number)
        )
        return result.scalar_one_or_none()

    async def calendar(self, season_id: int, number: int) -> list[CalendarRow]:
        result = await self.session.execute(
            text("""
                SELECT m.played_at, m.counts, ht.name, at.name
                FROM matches m
                JOIN matchdays md ON md.id = m.matchday_id
                JOIN teams ht ON ht.id = m.home_team_id
                JOIN teams at ON at.id = m.away_team_id
                WHERE md.season_id = :sid AND md.number = :n
                ORDER BY m.played_at NULLS LAST, m.id
            """),
            {"sid": season_id, "n": number},
        )
        return [CalendarRow(r[0], bool(r[1]), r[2], r[3]) for r in result]

    async def playoff_rival(self, matchday_id: int, participant_id: int) -> int | None:
        """The other side of the asker's playoff tie this matchday, if any."""
        result = await self.session.execute(
            select(CompetitionMatchup).where(
                CompetitionMatchup.matchday_id == matchday_id,
                or_(
                    CompetitionMatchup.participant_a_id == participant_id,
                    CompetitionMatchup.participant_b_id == participant_id,
                ),
            )
        )
        tie = result.scalars().first()
        if tie is None:
            return None
        return (
            tie.participant_b_id
            if tie.participant_a_id == participant_id
            else tie.participant_a_id
        )

    async def scoring_rules(self, season_id: int) -> list[ScoringRule]:
        result = await self.session.execute(
            select(ScoringRule)
            .where(ScoringRule.season_id == season_id)
            .order_by(ScoringRule.rule_key, ScoringRule.position)
        )
        return list(result.scalars())
