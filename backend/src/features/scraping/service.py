from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

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
    # Public API
    # ------------------------------------------------------------------

    async def scrape_matchday(
        self, season_id: int, matchday_number: int
    ) -> dict[str, int]:
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
            logger.info(
                "scrape_matchday: no counting matches for matchday_id=%d", matchday_id
            )
            return {"processed": 0, "skipped": 0, "errors": 0}

        # Collect the set of team IDs referenced by counting matches.
        team_ids: set[int] = set()
        for match in counting_matches:
            team_ids.add(match.home_team_id)
            team_ids.add(match.away_team_id)

        # Load all players for those teams in one query.
        all_players = await self.repo.get_players_for_teams(season_id, team_ids)
        # Build a mapping from team_id → list[Player] for quick per-match lookup.
        players_by_team: dict[int, list] = {}
        for player in all_players:
            players_by_team.setdefault(player.team_id, []).append(player)

        total_processed = 0
        total_skipped = 0
        total_errors = 0

        base_url = self._settings.scraping_base_url
        season_slug = self._settings.scraping_season_slug

        async with ScrapingClient() as client:
            for match in counting_matches:
                match_players = (
                    players_by_team.get(match.home_team_id, [])
                    + players_by_team.get(match.away_team_id, [])
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
                    logger.info(
                        "scrape_matchday: marked match_id=%d stats_ok", match.id
                    )
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

        # Advance the season's scanned pointer when the matchday is fully done.
        if all_ok and counting_matches:
            await self.repo.update_season_matchday_scanned(season_id, matchday_number)

        summary = {
            "processed": total_processed,
            "skipped": total_skipped,
            "errors": total_errors,
        }
        logger.info(
            "scrape_matchday: done — matchday_id=%d summary=%s", matchday_id, summary
        )
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

        total_processed = 0
        total_skipped = 0
        total_errors = 0

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

        summary = {
            "processed": total_processed,
            "skipped": total_skipped,
            "errors": total_errors,
        }
        logger.info(
            "scrape_match_players: done — match_id=%d summary=%s", match_id, summary
        )
        return summary

    async def scrape_calendar(self, season_id: int) -> int:
        """Fetch the La Liga calendar and update match scores in the DB.

        The year suffix is derived from the season ``name`` field
        (e.g. ``"2024-2025"`` → year ``"2025"``).

        Returns
        -------
        Number of matches whose score was updated.
        """
        from sqlalchemy import select

        from src.shared.models.season import Season

        # Resolve season to get year for URL.
        stmt = select(Season).where(Season.id == season_id)
        result = await self.session.execute(stmt)
        season = result.scalar_one_or_none()
        if season is None:
            logger.error("scrape_calendar: season_id=%d not found", season_id)
            return 0

        # Season name is like "2024-2025"; we need the second year for the URL.
        parts = season.name.split("-")
        year = parts[-1] if len(parts) >= 2 else parts[0]

        base_url = self._settings.scraping_base_url
        url = f"{base_url}/laliga/calendario/{year}"
        logger.info("scrape_calendar: fetching %s", url)

        async with ScrapingClient() as client:
            try:
                html = await client.fetch(url)
            except ScrapingError as exc:
                logger.error("scrape_calendar: fetch failed: %s", exc)
                return 0

        calendar_matches = parse_calendar(html)
        logger.info("scrape_calendar: parsed %d matches from calendar", len(calendar_matches))

        updated = 0
        for cal_match in calendar_matches:
            if not cal_match.result:
                # Match not yet played.
                continue

            db_match = await self.repo.get_match_by_source_id(cal_match.source_id)
            if db_match is None:
                logger.debug(
                    "scrape_calendar: source_id=%d not in DB, skipping",
                    cal_match.source_id,
                )
                continue

            # Parse result string "2-1" into integers.
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

            # Only update if the score changed or was previously unset.
            if db_match.home_score != home_score or db_match.away_score != away_score:
                await self.repo.update_match_score(
                    match_id=db_match.id,
                    home_score=home_score,
                    away_score=away_score,
                    result=cal_match.result,
                )
                updated += 1

        logger.info("scrape_calendar: updated %d match scores", updated)
        return updated

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
