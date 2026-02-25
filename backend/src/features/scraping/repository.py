from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.scraping.parsers import PlayerMatchdayStats
from src.features.scraping.scoring import PointsBreakdown
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import ScoringRule, Season
from src.shared.models.team import Team

logger = logging.getLogger(__name__)

# Path to CRC storage file, relative to the backend root.
# Resolved at module load time so that both the CLI and the HTTP server
# find the same file regardless of cwd.
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_CRC_FILE = _BACKEND_ROOT / "data" / "crc.txt"


class ScrapingRepository:
    """Data-access layer for all scraping-related DB operations.

    Every method receives an already-open ``AsyncSession``; transaction
    management (commit / rollback) is the caller's responsibility.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Season / scoring rules
    # ------------------------------------------------------------------

    async def get_active_season(self) -> Season | None:
        """Return the season whose status is ``'active'``, or ``None``."""
        stmt = (
            select(Season)
            .where(Season.status == "active")
            .order_by(Season.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_scoring_rules(
        self, season_id: int
    ) -> dict[str, dict[str | None, Decimal | None]]:
        """Load all scoring rules for *season_id* into the format expected by ``ScoringEngine``.

        Returns a nested dict::

            {
                rule_key: {
                    position_or_None: Decimal,
                    ...
                },
                ...
            }
        """
        stmt = select(ScoringRule).where(ScoringRule.season_id == season_id)
        result = await self.session.execute(stmt)
        rules: dict[str, dict[str | None, Decimal | None]] = {}
        for row in result.scalars():
            if row.rule_key not in rules:
                rules[row.rule_key] = {}
            rules[row.rule_key][row.position] = row.value
        logger.debug(
            "get_scoring_rules: loaded %d rule entries for season_id=%d",
            sum(len(v) for v in rules.values()),
            season_id,
        )
        return rules

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    async def get_teams_by_name(self, season_id: int) -> dict[str, Team]:
        """Return a mapping of ``team.name → Team`` for *season_id*."""
        stmt = select(Team).where(Team.season_id == season_id)
        result = await self.session.execute(stmt)
        teams = {row.name: row for row in result.scalars()}
        logger.debug(
            "get_teams_by_name: found %d teams for season_id=%d", len(teams), season_id
        )
        return teams

    # ------------------------------------------------------------------
    # Players
    # ------------------------------------------------------------------

    async def get_players_by_slug(self, season_id: int) -> dict[str, Player]:
        """Return a mapping of ``player.slug → Player`` for *season_id*."""
        stmt = select(Player).where(Player.season_id == season_id)
        result = await self.session.execute(stmt)
        players = {row.slug: row for row in result.scalars()}
        logger.debug(
            "get_players_by_slug: found %d players for season_id=%d",
            len(players),
            season_id,
        )
        return players

    async def get_players_for_teams(
        self, season_id: int, team_ids: set[int]
    ) -> list[Player]:
        """Return all players belonging to any of *team_ids* for *season_id*."""
        stmt = select(Player).where(
            Player.season_id == season_id,
            Player.team_id.in_(team_ids),
        )
        result = await self.session.execute(stmt)
        players = list(result.scalars())
        logger.debug(
            "get_players_for_teams: found %d players for teams=%s season_id=%d",
            len(players),
            team_ids,
            season_id,
        )
        return players

    # ------------------------------------------------------------------
    # Matchdays / matches
    # ------------------------------------------------------------------

    async def get_matchday(self, season_id: int, number: int) -> Matchday | None:
        """Return the matchday for *season_id* at *number*, or ``None``."""
        stmt = select(Matchday).where(
            Matchday.season_id == season_id,
            Matchday.number == number,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_matches_for_matchday(self, matchday_id: int) -> list[Match]:
        """Return all matches for *matchday_id*, ordered by id."""
        stmt = (
            select(Match)
            .where(Match.matchday_id == matchday_id)
            .order_by(Match.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_match_by_source_id(self, source_id: int) -> Match | None:
        """Find a match by its futbolfantasy ``source_id``."""
        stmt = select(Match).where(Match.source_id == source_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Player stats upsert
    # ------------------------------------------------------------------

    async def upsert_player_stat(
        self,
        player_id: int,
        matchday_id: int,
        match_id: int | None,
        position: str,
        stats: PlayerMatchdayStats,
        breakdown: PointsBreakdown,
    ) -> None:
        """INSERT or UPDATE a ``player_stats`` row via PostgreSQL ON CONFLICT.

        Uses the unique constraint ``uq_player_matchday`` (player_id, matchday_id)
        so that re-running the scraper is idempotent.
        """
        values: dict = {
            "player_id": player_id,
            "matchday_id": matchday_id,
            "match_id": match_id,
            "processed": True,
            "position": position,
            "played": stats.played,
            "event": stats.event,
            "event_minute": stats.event_minute,
            "minutes_played": stats.minutes_played,
            "home_score": stats.home_score,
            "away_score": stats.away_score,
            "result": stats.result,
            "goals_for": stats.goals_for,
            "goals_against": stats.goals_against,
            "goals": stats.goals,
            "penalty_goals": stats.penalty_goals,
            "penalties_missed": stats.penalties_missed,
            "own_goals": stats.own_goals,
            "assists": stats.assists,
            "penalties_saved": stats.penalties_saved,
            "yellow_card": stats.yellow_card,
            "yellow_removed": stats.yellow_removed,
            "double_yellow": stats.double_yellow,
            "red_card": stats.red_card,
            "woodwork": stats.woodwork,
            "penalties_won": stats.penalties_won,
            "penalties_committed": stats.penalties_committed,
            "marca_rating": stats.marca_rating,
            "as_picas": stats.as_picas,
            "pts_play": breakdown.pts_play,
            "pts_starter": breakdown.pts_starter,
            "pts_result": breakdown.pts_result,
            "pts_clean_sheet": breakdown.pts_clean_sheet,
            "pts_goals": breakdown.pts_goals,
            "pts_penalty_goals": breakdown.pts_penalty_goals,
            "pts_assists": breakdown.pts_assists,
            "pts_penalties_saved": breakdown.pts_penalties_saved,
            "pts_woodwork": breakdown.pts_woodwork,
            "pts_penalties_won": breakdown.pts_penalties_won,
            "pts_penalties_missed": breakdown.pts_penalties_missed,
            "pts_own_goals": breakdown.pts_own_goals,
            "pts_yellow": breakdown.pts_yellow,
            "pts_red": breakdown.pts_red,
            "pts_pen_committed": breakdown.pts_pen_committed,
            "pts_marca": breakdown.pts_marca,
            "pts_as": breakdown.pts_as,
            "pts_marca_as": breakdown.pts_marca_as,
            "pts_total": breakdown.pts_total,
        }

        # Build the set_ dict for the update clause (all columns except the
        # natural key columns player_id / matchday_id).
        set_cols = {k: v for k, v in values.items() if k not in ("player_id", "matchday_id")}

        stmt = (
            pg_insert(PlayerStat)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["player_id", "matchday_id"],
                set_=set_cols,
            )
        )
        await self.session.execute(stmt)
        logger.debug(
            "upsert_player_stat: player_id=%d matchday_id=%d pts_total=%d",
            player_id,
            matchday_id,
            breakdown.pts_total,
        )

    # ------------------------------------------------------------------
    # Match updates
    # ------------------------------------------------------------------

    async def update_match_score(
        self, match_id: int, home_score: int, away_score: int, result: str
    ) -> None:
        """Update the score and result string of a match row."""
        stmt = (
            update(Match)
            .where(Match.id == match_id)
            .values(home_score=home_score, away_score=away_score, result=result)
        )
        await self.session.execute(stmt)
        logger.debug(
            "update_match_score: match_id=%d score=%d-%d", match_id, home_score, away_score
        )

    async def mark_match_stats_ok(self, match_id: int) -> None:
        """Set ``match.stats_ok = True``."""
        stmt = update(Match).where(Match.id == match_id).values(stats_ok=True)
        await self.session.execute(stmt)
        logger.debug("mark_match_stats_ok: match_id=%d", match_id)

    async def mark_matchday_stats_ok(self, matchday_id: int) -> None:
        """Set ``matchday.stats_ok = True``."""
        stmt = update(Matchday).where(Matchday.id == matchday_id).values(stats_ok=True)
        await self.session.execute(stmt)
        logger.debug("mark_matchday_stats_ok: matchday_id=%d", matchday_id)

    async def update_matchday_status(self, matchday_id: int, status: str) -> None:
        """Update ``matchday.status`` to *status*."""
        stmt = update(Matchday).where(Matchday.id == matchday_id).values(status=status)
        await self.session.execute(stmt)
        logger.debug("update_matchday_status: matchday_id=%d status=%s", matchday_id, status)

    async def update_season_matchday_scanned(self, season_id: int, number: int) -> None:
        """Update ``season.matchday_scanned`` to *number*."""
        stmt = update(Season).where(Season.id == season_id).values(matchday_scanned=number)
        await self.session.execute(stmt)
        logger.debug(
            "update_season_matchday_scanned: season_id=%d number=%d", season_id, number
        )

    async def update_season_matchday_current(self, season_id: int, number: int) -> None:
        """Update ``season.matchday_current`` to *number*."""
        stmt = update(Season).where(Season.id == season_id).values(matchday_current=number)
        await self.session.execute(stmt)
        logger.debug(
            "update_season_matchday_current: season_id=%d number=%d", season_id, number
        )

    # ------------------------------------------------------------------
    # CRC persistence (file-based, not in DB)
    # ------------------------------------------------------------------

    async def get_crc_value(self) -> str | None:
        """Read the stored CRC value from ``data/crc.txt``.

        Returns ``None`` when the file does not exist or is empty.
        """
        try:
            if _CRC_FILE.exists():
                value = _CRC_FILE.read_text(encoding="utf-8").strip()
                return value if value else None
        except OSError as exc:
            logger.warning("get_crc_value: could not read %s: %s", _CRC_FILE, exc)
        return None

    async def save_crc_value(self, crc: str) -> None:
        """Persist *crc* to ``data/crc.txt``, creating parent dirs as needed."""
        try:
            _CRC_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CRC_FILE.write_text(crc, encoding="utf-8")
            logger.debug("save_crc_value: saved crc=%s to %s", crc, _CRC_FILE)
        except OSError as exc:
            logger.error("save_crc_value: could not write %s: %s", _CRC_FILE, exc)
