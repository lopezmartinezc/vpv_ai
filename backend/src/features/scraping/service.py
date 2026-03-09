from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.economy.service import EconomyService
from src.features.scraping.aggregation import ScoreAggregator
from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.config import scraping_settings
from src.features.scraping.parsers import (
    parse_calendar,
    parse_homepage_matchday,
    parse_player_stats,
)
from src.features.scraping.repository import ScrapingRepository
from src.features.scraping.scoring import ScoringEngine
from src.shared.models.team import Team

logger = logging.getLogger(__name__)


class ScrapingService:
    """Orchestrates all scraping workflows: matchday stats, calendar, CRC checks.

    Every public method should be called inside an open DB transaction;
    the session is committed or rolled back by the caller (FastAPI dependency
    or CLI command).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ScrapingRepository(session)
        self._aggregator = ScoreAggregator(session)
        self._settings = scraping_settings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _team_names(self, team_ids: set[int]) -> dict[int, str]:
        """Return a mapping of team_id → team name for the given IDs."""
        from sqlalchemy import select

        stmt = select(Team.id, Team.name).where(Team.id.in_(team_ids))
        result = await self.session.execute(stmt)
        return {row.id: row.name for row in result.all()}

    @staticmethod
    def _format_scrape_error(player_name: str, team_name: str, exc: ScrapingError) -> str:
        """Build a short, human-readable error string."""
        import httpx

        cause = exc.cause
        if isinstance(cause, httpx.HTTPStatusError):
            return f"{player_name} ({team_name}): HTTP {cause.response.status_code}"
        return f"{player_name} ({team_name}): {type(cause).__name__}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scrape_matchday(self, season_id: int, matchday_number: int) -> dict[str, int]:
        """Scrape all player stats for every match in *matchday_number*.

        Flow
        ----
        1. Load scoring rules → ``ScoringEngine``.
        2. Fetch the ``Matchday`` and its ``Match`` rows.
        3. For each match where ``counts=True``:
           a. Collect the home-team and away-team player IDs.
           b. Open a single ``ScrapingClient`` session.
           c. For each player: fetch their stats page, parse, calculate points,
              upsert ``player_stats``.
           d. Mark the match as ``stats_ok`` once all its players are processed.
        4. If all counting matches are stats-ok, mark the matchday ``stats_ok``.
        5. Run score aggregation.
        6. Update ``season.matchday_scanned``.

        Returns
        -------
        dict with keys ``processed``, ``skipped``, ``errors``.
        """
        rules = await self.repo.get_scoring_rules(season_id)
        engine = ScoringEngine(rules)

        matchday = await self.repo.get_matchday(season_id, matchday_number)
        if matchday is None:
            logger.error(
                "scrape_matchday: matchday not found season_id=%d number=%d",
                season_id,
                matchday_number,
            )
            return {"processed": 0, "skipped": 0, "errors": 0}

        matchday_id = matchday.id
        matches = await self.repo.get_matches_for_matchday(matchday_id)

        counting_matches = [m for m in matches if m.counts]
        if not counting_matches:
            logger.info("scrape_matchday: no counting matches for matchday_id=%d", matchday_id)
            return {"processed": 0, "skipped": 0, "errors": 0}

        # Collect the set of team IDs referenced by counting matches.
        team_ids: set[int] = set()
        for match in counting_matches:
            team_ids.add(match.home_team_id)
            team_ids.add(match.away_team_id)

        # Load all players for those teams in one query.
        all_players = await self.repo.get_players_for_teams(season_id, team_ids)
        team_names = await self._team_names(team_ids)
        # Build a mapping from team_id → list[Player] for quick per-match lookup.
        players_by_team: dict[int, list] = {}
        for player in all_players:
            players_by_team.setdefault(player.team_id, []).append(player)

        total_processed = 0
        total_skipped = 0
        total_errors = 0
        error_details: list[str] = []

        base_url = self._settings.scraping_base_url
        season_slug = self._settings.scraping_season_slug

        async with ScrapingClient() as client:
            for match in counting_matches:
                match_players = players_by_team.get(match.home_team_id, []) + players_by_team.get(
                    match.away_team_id, []
                )
                total_in_match = len(match_players)
                match_errors = 0

                logger.info(
                    "scrape_matchday: processing match_id=%d (%d players)",
                    match.id,
                    total_in_match,
                )

                for idx, player in enumerate(match_players, start=1):
                    logger.info(
                        "scrape_matchday: player %d/%d slug=%s match_id=%d",
                        idx,
                        total_in_match,
                        player.slug,
                        match.id,
                    )

                    url = f"{base_url}/jugadores/{player.slug}/{season_slug}"
                    try:
                        html = await client.fetch(url)
                    except ScrapingError as exc:
                        logger.warning(
                            "scrape_matchday: fetch failed for player slug=%s: %s",
                            player.slug,
                            exc,
                        )
                        total_errors += 1
                        match_errors += 1
                        team = team_names.get(player.team_id, "?")
                        error_details.append(self._format_scrape_error(player.name, team, exc))
                        continue

                    stats = parse_player_stats(html, matchday_number)
                    if stats is None:
                        logger.debug(
                            "scrape_matchday: no stats for player slug=%s matchday=%d",
                            player.slug,
                            matchday_number,
                        )
                        total_skipped += 1
                        continue

                    # Use the player's registered position as a starting point;
                    # the scraper doesn't provide a per-matchday position override,
                    # so we fall back to the player's canonical position.
                    position = player.position

                    breakdown = engine.calculate(stats, position)

                    await self.repo.upsert_player_stat(
                        player_id=player.id,
                        matchday_id=matchday_id,
                        match_id=match.id,
                        position=position,
                        stats=stats,
                        breakdown=breakdown,
                    )
                    total_processed += 1

                # Mark the match stats_ok only when there were no errors.
                if match_errors == 0:
                    await self.repo.mark_match_stats_ok(match.id)
                    logger.info("scrape_matchday: marked match_id=%d stats_ok", match.id)
                else:
                    logger.warning(
                        "scrape_matchday: match_id=%d had %d errors, NOT marking stats_ok",
                        match.id,
                        match_errors,
                    )

        # Reload to check if every counting match is now stats_ok.
        refreshed_matches = await self.repo.get_matches_for_matchday(matchday_id)
        all_ok = all(m.stats_ok for m in refreshed_matches if m.counts)
        if all_ok and counting_matches:
            await self.repo.mark_matchday_stats_ok(matchday_id)
            await self.repo.update_matchday_status(matchday_id, "finished")
            logger.info(
                "scrape_matchday: all counting matches done — matchday_id=%d marked stats_ok",
                matchday_id,
            )

        # Run score aggregation regardless of completeness (partial updates are fine).
        await self._aggregator.aggregate_matchday(matchday_id)

        # Generate weekly payments once the matchday is fully scored.
        if all_ok and counting_matches:
            economy_svc = EconomyService(self.session)
            await economy_svc.generate_weekly_payments(season_id, matchday_id)

        # Advance the season's scanned pointer when the matchday is fully done.
        if all_ok and counting_matches:
            await self.repo.update_season_matchday_scanned(season_id, matchday_number)

        summary: dict[str, object] = {
            "processed": total_processed,
            "skipped": total_skipped,
            "errors": total_errors,
            "error_details": error_details,
        }
        logger.info("scrape_matchday: done — matchday_id=%d summary=%s", matchday_id, summary)
        return summary

    async def scrape_match_players(
        self, season_id: int, matchday_number: int, match_id: int
    ) -> dict[str, int]:
        """Scrape stats for the two teams in a single match.

        Parameters
        ----------
        season_id:
            ID of the season.
        matchday_number:
            Jornada number (used to find the ``Matchday`` row and to parse
            stats from the player page).
        match_id:
            Primary key of the ``matches`` row to process.

        Returns
        -------
        dict with keys ``processed``, ``skipped``, ``errors``.
        """
        rules = await self.repo.get_scoring_rules(season_id)
        engine = ScoringEngine(rules)

        matchday = await self.repo.get_matchday(season_id, matchday_number)
        if matchday is None:
            logger.error(
                "scrape_match_players: matchday not found season_id=%d number=%d",
                season_id,
                matchday_number,
            )
            return {"processed": 0, "skipped": 0, "errors": 0}

        matchday_id = matchday.id

        # Find the target match among this matchday's matches.
        matches = await self.repo.get_matches_for_matchday(matchday_id)
        match = next((m for m in matches if m.id == match_id), None)
        if match is None:
            logger.error(
                "scrape_match_players: match_id=%d not found in matchday_id=%d",
                match_id,
                matchday_id,
            )
            return {"processed": 0, "skipped": 0, "errors": 0}

        team_ids = {match.home_team_id, match.away_team_id}
        match_players = await self.repo.get_players_for_teams(season_id, team_ids)
        team_names = await self._team_names(team_ids)

        total_processed = 0
        total_skipped = 0
        total_errors = 0
        error_details: list[str] = []

        base_url = self._settings.scraping_base_url
        season_slug = self._settings.scraping_season_slug

        async with ScrapingClient() as client:
            total = len(match_players)
            for idx, player in enumerate(match_players, start=1):
                logger.info(
                    "scrape_match_players: player %d/%d slug=%s match_id=%d",
                    idx,
                    total,
                    player.slug,
                    match_id,
                )

                url = f"{base_url}/jugadores/{player.slug}/{season_slug}"
                try:
                    html = await client.fetch(url)
                except ScrapingError as exc:
                    logger.warning(
                        "scrape_match_players: fetch failed for slug=%s: %s",
                        player.slug,
                        exc,
                    )
                    total_errors += 1
                    team = team_names.get(player.team_id, "?")
                    error_details.append(f"{player.name} ({team}): {exc.cause}")
                    continue

                stats = parse_player_stats(html, matchday_number)
                if stats is None:
                    total_skipped += 1
                    continue

                position = player.position
                breakdown = engine.calculate(stats, position)

                await self.repo.upsert_player_stat(
                    player_id=player.id,
                    matchday_id=matchday_id,
                    match_id=match_id,
                    position=position,
                    stats=stats,
                    breakdown=breakdown,
                )
                total_processed += 1

        if total_errors == 0:
            await self.repo.mark_match_stats_ok(match_id)

        await self._aggregator.aggregate_matchday(matchday_id)

        summary: dict[str, object] = {
            "processed": total_processed,
            "skipped": total_skipped,
            "errors": total_errors,
            "error_details": error_details,
        }
        logger.info("scrape_match_players: done — match_id=%d summary=%s", match_id, summary)
        return summary

    async def scrape_calendar(self, season_id: int) -> dict[str, int]:
        """Fetch the La Liga calendar and update match scores + dates in the DB.

        The year suffix is derived from the season ``name`` field
        (e.g. ``"2024-2025"`` → year ``"2025"``).

        Returns
        -------
        dict with keys ``scores_updated`` and ``dates_updated``.
        """
        from datetime import datetime as _dt

        from sqlalchemy import select

        from src.shared.models.season import Season

        # Resolve season to get year for URL.
        stmt = select(Season).where(Season.id == season_id)
        result = await self.session.execute(stmt)
        season = result.scalar_one_or_none()
        if season is None:
            logger.error("scrape_calendar: season_id=%d not found", season_id)
            return {"scores_updated": 0, "dates_updated": 0}

        # Season name is like "2024-2025"; we need the second year for the URL.
        parts = season.name.split("-")
        year = parts[-1] if len(parts) >= 2 else parts[0]
        season_year = int(year)

        base_url = self._settings.scraping_base_url
        url = f"{base_url}/laliga/calendario/{year}"
        logger.info("scrape_calendar: fetching %s", url)

        async with ScrapingClient() as client:
            try:
                html = await client.fetch(url)
            except ScrapingError as exc:
                logger.error("scrape_calendar: fetch failed: %s", exc)
                return {"scores_updated": 0, "dates_updated": 0}

        calendar_matches = parse_calendar(html, season_year=season_year)
        logger.info("scrape_calendar: parsed %d matches from calendar", len(calendar_matches))

        scores_updated = 0
        dates_updated = 0

        for cal_match in calendar_matches:
            db_match = await self.repo.get_match_by_source_id(cal_match.source_id)
            if db_match is None:
                logger.debug(
                    "scrape_calendar: source_id=%d not in DB, skipping",
                    cal_match.source_id,
                )
                continue

            # Update played_at if the calendar provides a date
            if cal_match.played_at:
                new_dt = _dt.fromisoformat(cal_match.played_at)
                if db_match.played_at != new_dt:
                    await self.repo.update_match_played_at(db_match.id, new_dt)
                    dates_updated += 1

            # Update scores for completed matches
            if cal_match.result:
                try:
                    home_str, away_str = cal_match.result.split("-", 1)
                    home_score = int(home_str.strip())
                    away_score = int(away_str.strip())
                except (ValueError, AttributeError):
                    logger.debug(
                        "scrape_calendar: malformed result %r for source_id=%d",
                        cal_match.result,
                        cal_match.source_id,
                    )
                    continue

                if db_match.home_score != home_score or db_match.away_score != away_score:
                    await self.repo.update_match_score(
                        match_id=db_match.id,
                        home_score=home_score,
                        away_score=away_score,
                        result=cal_match.result,
                    )
                    scores_updated += 1

        # Recalculate matchday first_match_at if any dates changed.
        if dates_updated:
            await self.repo.sync_matchday_first_match_at(season_id)

        # Fallback: for matches that should have ended but calendar has no
        # result, try fetching the score from the individual match detail page.
        from datetime import UTC, timedelta

        from src.features.scraping.parsers import parse_match_score

        buffer = self._settings.scraping_buffer_minutes
        cutoff = _dt.now(tz=UTC) - timedelta(minutes=buffer)
        pending = await self.repo.get_pending_score_matches(season_id, before=cutoff)

        if pending:
            logger.info(
                "scrape_calendar: %d matches without score past buffer, checking detail pages",
                len(pending),
            )
            async with ScrapingClient() as client:
                for match in pending:
                    try:
                        html = await client.fetch(match.source_url)  # type: ignore[arg-type]
                    except ScrapingError:
                        logger.debug("scrape_calendar: fetch failed for match id=%d", match.id)
                        continue

                    score = parse_match_score(html)
                    if score is None:
                        continue

                    home_score, away_score = score
                    await self.repo.update_match_score(
                        match_id=match.id,
                        home_score=home_score,
                        away_score=away_score,
                        result=f"{home_score}-{away_score}",
                    )
                    scores_updated += 1
                    logger.info(
                        "scrape_calendar: match id=%d score discovered from detail page: %d-%d",
                        match.id,
                        home_score,
                        away_score,
                    )

        logger.info(
            "scrape_calendar: scores_updated=%d dates_updated=%d",
            scores_updated,
            dates_updated,
        )
        return {"scores_updated": scores_updated, "dates_updated": dates_updated}

    async def check_for_updates(self) -> list[int]:
        """Check the homepage for CRC changes indicating new stats are available.

        Compares the current page CRC against the last saved value.  When they
        differ the new CRC is persisted and the list of match IDs whose stats
        are ready is returned.

        Returns
        -------
        List of ``source_id`` values (futbolfantasy match IDs) that are ready
        when the CRC changed, or an empty list when nothing changed.
        """
        base_url = self._settings.scraping_base_url
        url = base_url  # the homepage

        async with ScrapingClient() as client:
            try:
                html = await client.fetch(url)
            except ScrapingError as exc:
                logger.error("check_for_updates: fetch failed: %s", exc)
                return []

        info = parse_homepage_matchday(html)
        if info is None or not info.crc:
            logger.warning("check_for_updates: could not parse homepage matchday info")
            return []

        stored_crc = await self.repo.get_crc_value()
        if stored_crc == info.crc:
            logger.debug("check_for_updates: CRC unchanged (%s)", info.crc)
            return []

        logger.info(
            "check_for_updates: CRC changed %r → %r, ready_match_ids=%s",
            stored_crc,
            info.crc,
            info.ready_match_ids,
        )
        await self.repo.save_crc_value(info.crc)
        return info.ready_match_ids
