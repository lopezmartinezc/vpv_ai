from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, update
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
        """Return the most recently created active season, or ``None``.

        Used by the scheduler. Both Liga (``kind='league'``) and
        tournaments (``kind='tournament'``) are considered — anything
        with ``status='active'`` is eligible. When more than one season
        is active simultaneously (e.g. Liga + Mundial overlap), the
        highest ``id`` wins; typically the newest season is the one
        currently in progress.
        """
        stmt = select(Season).where(Season.status == "active").order_by(Season.id.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_season(self, season_id: int) -> Season | None:
        """Return a season by primary key."""
        stmt = select(Season).where(Season.id == season_id)
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
        logger.debug("get_teams_by_name: found %d teams for season_id=%d", len(teams), season_id)
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

    async def get_players_for_teams(self, season_id: int, team_ids: set[int]) -> list[Player]:
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
        stmt = select(Match).where(Match.matchday_id == matchday_id).order_by(Match.id)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_match_by_source_id(self, source_id: int) -> Match | None:
        """Find a match by its futbolfantasy ``source_id``."""
        stmt = select(Match).where(Match.source_id == source_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_match_for_team(self, matchday_id: int, team_id: int) -> Match | None:
        """Return the match in *matchday_id* where *team_id* participates."""
        from sqlalchemy import or_

        stmt = select(Match).where(
            Match.matchday_id == matchday_id,
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_matchdays_by_season(
        self, season_id: int, start: int | None = None, end: int | None = None
    ) -> list[Matchday]:
        """Return all matchdays for *season_id*, optionally filtered by number range.

        Ordered by ``number`` ascending.
        """
        stmt = select(Matchday).where(Matchday.season_id == season_id)
        if start is not None:
            stmt = stmt.where(Matchday.number >= start)
        if end is not None:
            stmt = stmt.where(Matchday.number <= end)
        stmt = stmt.order_by(Matchday.number)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_players_for_season(self, season_id: int) -> list[Player]:
        """Return all players for *season_id*, ordered by id (stable)."""
        stmt = select(Player).where(Player.season_id == season_id).order_by(Player.id)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_player_stat(self, player_id: int, matchday_id: int) -> PlayerStat | None:
        """Return the existing player_stats row for (player, matchday), or None.

        Used to preserve historical position/match_id when re-scraping: a
        player may have changed position (winter draft) or team (real-life
        transfer) between the original scrape and now. The fantasy points
        for past matchdays must reflect the position the player had ON THAT
        matchday, and the match_id must refer to the match where his team
        AT THAT TIME played.
        """
        stmt = select(PlayerStat).where(
            PlayerStat.player_id == player_id,
            PlayerStat.matchday_id == matchday_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_score_matches(self, season_id: int, before: object) -> list[Match]:
        """Return matches with no score that should have ended (played_at < before)."""
        from src.shared.models.matchday import Matchday

        stmt = (
            select(Match)
            .join(Matchday, Match.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Match.home_score.is_(None),
                Match.source_url.isnot(None),
                Match.played_at.isnot(None),
                Match.played_at < before,
            )
            .order_by(Match.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

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
        team_id: int | None = None,
    ) -> None:
        """INSERT or UPDATE a ``player_stats`` row via PostgreSQL ON CONFLICT.

        Uses the unique constraint ``uq_player_matchday`` (player_id, matchday_id)
        so that re-running the scraper is idempotent.
        """
        values: dict = {
            "player_id": player_id,
            "matchday_id": matchday_id,
            "match_id": match_id,
            "team_id": team_id,
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
        set_cols = {
            k: v for k, v in values.items() if k not in ("player_id", "matchday_id", "team_id")
        }

        insert_stmt = pg_insert(PlayerStat).values(**values)
        # Pin team_id to the FIRST scrape of this matchday: keep the stored
        # value and only fill it when still NULL. A later transfer re-scrape
        # must not overwrite the team the player actually played for.
        set_cols["team_id"] = func.coalesce(PlayerStat.team_id, insert_stmt.excluded.team_id)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["player_id", "matchday_id"],
            set_=set_cols,
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

    async def update_match_played_at(self, match_id: int, played_at: object) -> None:
        """Update the scheduled date/time of a match."""
        stmt = update(Match).where(Match.id == match_id).values(played_at=played_at)
        await self.session.execute(stmt)
        logger.debug("update_match_played_at: match_id=%d played_at=%s", match_id, played_at)

    async def update_match_source_url(self, match_id: int, source_url: str) -> None:
        """Update the source_url of a match (used when futbolfantasy changes URL format)."""
        stmt = update(Match).where(Match.id == match_id).values(source_url=source_url)
        await self.session.execute(stmt)
        logger.debug("update_match_source_url: match_id=%d source_url=%s", match_id, source_url)

    async def sync_matchday_first_match_at(self, season_id: int) -> int:
        """Recalculate ``matchdays.first_match_at`` from match dates for all matchdays."""
        from sqlalchemy import func

        subq = (
            select(
                Match.matchday_id,
                func.min(Match.played_at).label("earliest"),
            )
            .join(Matchday, Match.matchday_id == Matchday.id)
            .where(Matchday.season_id == season_id, Match.played_at.isnot(None))
            .group_by(Match.matchday_id)
            .subquery()
        )
        stmt = (
            update(Matchday)
            .where(Matchday.id == subq.c.matchday_id)
            .values(first_match_at=subq.c.earliest)
        )
        result = await self.session.execute(stmt)
        logger.debug(
            "sync_matchday_first_match_at: season_id=%d rows=%d",
            season_id,
            result.rowcount,  # type: ignore[attr-defined]
        )
        return result.rowcount  # type: ignore[attr-defined]

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
        logger.debug("update_season_matchday_scanned: season_id=%d number=%d", season_id, number)

    async def update_season_matchday_current(self, season_id: int, number: int) -> None:
        """Update ``season.matchday_current`` to *number*."""
        stmt = update(Season).where(Season.id == season_id).values(matchday_current=number)
        await self.session.execute(stmt)
        logger.debug("update_season_matchday_current: season_id=%d number=%d", season_id, number)

    # ------------------------------------------------------------------
    # Player photos
    # ------------------------------------------------------------------

    async def get_players_without_photo(self, season_id: int) -> list[Player]:
        """Return all players for *season_id* whose ``photo_path`` is NULL."""
        stmt = (
            select(Player)
            .where(Player.season_id == season_id, Player.photo_path.is_(None))
            .order_by(Player.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_players_by_team(self, team_id: int) -> list[Player]:
        """Return all players (any availability) currently linked to *team_id*."""
        stmt = select(Player).where(Player.team_id == team_id).order_by(Player.id)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def set_players_availability(self, player_ids: list[int], is_available: bool) -> int:
        """Bulk-update ``is_available`` for the given player ids. Returns the
        number of ids passed (rowcount is unreliable on async SQLAlchemy)."""
        if not player_ids:
            return 0
        stmt = update(Player).where(Player.id.in_(player_ids)).values(is_available=is_available)
        await self.session.execute(stmt)
        return len(player_ids)

    async def update_player_team(self, player_id: int, team_id: int) -> None:
        """Move a player to a new team (real transfer). Only touches the
        CURRENT team; historical player_stats.team_id stays pinned."""
        await self.session.execute(
            update(Player).where(Player.id == player_id).values(team_id=team_id)
        )

    async def get_players_to_enrich(self, season_id: int) -> list[Player]:
        """Return players for *season_id* missing either ``photo_path`` or ``position``.

        Used by :class:`PhotoDownloader` to perform both enrichments in a
        single pass over the player's individual page.
        """
        from sqlalchemy import or_

        stmt = (
            select(Player)
            .where(
                Player.season_id == season_id,
                or_(
                    Player.photo_path.is_(None),
                    Player.position.is_(None),
                    Player.position == "",
                ),
            )
            .order_by(Player.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_slugs_in_other_seasons(self, season_id: int) -> set[str]:
        """Return the set of player slugs that appear in seasons OTHER
        than ``season_id``.

        Used by the ``--force-redownload`` path: a slug shared with
        another season would have its WebP overwritten by a re-fetch
        with the wrong-season URL, polluting the other season's UI.
        Those slugs are excluded from the wipe."""
        stmt = select(Player.slug).distinct().where(Player.season_id != season_id)
        result = await self.session.execute(stmt)
        return {slug for (slug,) in result.all()}

    async def update_player_photo(
        self, player_id: int, photo_path: str | None, source_url: str
    ) -> None:
        """Set ``photo_path`` and ``source_url`` for a player.

        ``photo_path=None`` is allowed and used by the force-redownload
        path of ``PhotoDownloader`` to mark a player as missing-photo so
        the next iteration of the queue actually fetches it again."""
        stmt = (
            update(Player)
            .where(Player.id == player_id)
            .values(photo_path=photo_path, source_url=source_url)
        )
        await self.session.execute(stmt)
        logger.debug("update_player_photo: player_id=%d path=%s", player_id, photo_path)

    async def update_player_position(self, player_id: int, position: str) -> None:
        """Set ``position`` for a player (used when enriching from /jugadores/{slug})."""
        stmt = update(Player).where(Player.id == player_id).values(position=position)
        await self.session.execute(stmt)
        logger.debug("update_player_position: player_id=%d position=%s", player_id, position)

    # ------------------------------------------------------------------
    # Match CRC (per-match change detection)
    # ------------------------------------------------------------------

    async def update_match_crc(self, match_id: int, stats_crc: str) -> None:
        """Store the computed CRC for a match page."""
        stmt = update(Match).where(Match.id == match_id).values(stats_crc=stats_crc)
        await self.session.execute(stmt)

    # ------------------------------------------------------------------
    # Team / player / match creation (season initialization)
    # ------------------------------------------------------------------

    async def create_team(
        self, season_id: int, name: str, slug: str, short_name: str | None = None
    ) -> Team:
        team = Team(season_id=season_id, name=name, slug=slug, short_name=short_name)
        self.session.add(team)
        await self.session.flush()
        return team

    async def create_player(
        self,
        season_id: int,
        team_id: int,
        name: str,
        display_name: str,
        slug: str,
        position: str,
    ) -> Player:
        player = Player(
            season_id=season_id,
            team_id=team_id,
            name=name,
            display_name=display_name,
            slug=slug,
            position=position,
            is_available=True,
        )
        self.session.add(player)
        return player

    async def create_match(
        self,
        matchday_id: int,
        home_team_id: int,
        away_team_id: int,
        source_id: int | None = None,
        source_url: str | None = None,
        played_at: object = None,
    ) -> Match:
        match = Match(
            matchday_id=matchday_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            source_id=source_id,
            source_url=source_url,
            played_at=played_at,
        )
        self.session.add(match)
        return match

    async def get_teams_by_season(self, season_id: int) -> list[Team]:
        stmt = select(Team).where(Team.season_id == season_id).order_by(Team.id)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_player_slugs_by_season(self, season_id: int) -> set[str]:
        """Existing player slugs for a season — used to make the roster
        import idempotent (skip already-imported players on re-runs)."""
        result = await self.session.execute(
            select(Player.slug).where(Player.season_id == season_id)
        )
        return {row[0] for row in result.all()}

    async def get_match_source_ids_by_season(self, season_id: int) -> set[int]:
        """Existing match ``source_id`` values for a season — used to make
        the calendar import idempotent (skip already-created fixtures)."""
        result = await self.session.execute(
            select(Match.source_id)
            .join(Matchday, Match.matchday_id == Matchday.id)
            .where(Matchday.season_id == season_id, Match.source_id.isnot(None))
        )
        return {row[0] for row in result.all()}

    # ------------------------------------------------------------------
    # CRC persistence (file-based, not in DB) — legacy homepage CRC
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
