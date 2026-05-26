from __future__ import annotations

import logging
from typing import ClassVar

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.economy.service import EconomyService
from src.features.scraping.aggregation import ScoreAggregator
from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.config import competition_url_prefix, scraping_settings
from src.features.scraping.log_buffer import scraping_log
from src.features.scraping.log_repository import ScrapingLogRepository
from src.features.scraping.parsers import (
    parse_calendar,
    parse_homepage_matchday,
    parse_player_all_matchdays,
    parse_player_stats,
    parse_roster,
    parse_teams,
)
from src.features.scraping.repository import ScrapingRepository
from src.features.scraping.scoring import ScoringEngine
from src.shared.models.team import Team

logger = logging.getLogger(__name__)

_MANUAL = "manual_scrape"


def _absolute_match_url(href: str | None, base_url: str) -> str | None:
    """Normalize a match href from the calendar parser to an absolute URL.

    Futbolfantasy serves anchors as absolute URLs today, but the parser also
    accepts relative paths. Returns None for empty input.
    """
    if not href:
        return None
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("/"):
        return f"{base_url.rstrip('/')}{href}"
    return f"{base_url.rstrip('/')}/{href}"


def _resolve_season_year(season: object) -> int:
    """Extract the calendar year used in scraping URLs from a Season.

    Priority:
    1. ``season.tournament_config["year"]`` if set explicitly
    2. Last 4-digit group found in ``season.name``
    3. Last 2-digit group expanded to 20YY
    4. Falls back to the current UTC year.
    """
    import re
    from datetime import UTC, datetime

    config = getattr(season, "tournament_config", None)
    if isinstance(config, dict):
        cfg_year = config.get("year")
        if isinstance(cfg_year, int):
            return cfg_year
        if isinstance(cfg_year, str) and cfg_year.isdigit():
            return int(cfg_year)

    name = getattr(season, "name", "") or ""
    # Try a 4-digit year first
    m4 = re.findall(r"(\d{4})", name)
    if m4:
        return int(m4[-1])
    # Then a 2-digit year (e.g. "Mundial 26" -> 2026)
    m2 = re.findall(r"(\d{2})", name)
    if m2:
        return 2000 + int(m2[-1])
    return datetime.now(UTC).year


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

    async def _resolve_season_slug(self, season_id: int) -> str:
        """Return scraping_slug from DB if set, otherwise fall back to .env."""
        season = await self.repo.get_season(season_id)
        if season and season.scraping_slug:
            return season.scraping_slug
        return self._settings.scraping_season_slug

    @staticmethod
    def _format_scrape_error(player_name: str, team_name: str, exc: ScrapingError) -> str:
        """Build a short, human-readable error string."""
        cause = exc.cause
        if isinstance(cause, httpx.HTTPStatusError):
            return f"{player_name} ({team_name}): HTTP {cause.response.status_code}"
        return f"{player_name} ({team_name}): {type(cause).__name__}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scrape_matchday(
        self,
        season_id: int,
        matchday_number: int,
    ) -> dict[str, object]:
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
        season = await self.repo.get_season(season_id)

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

        async with ScrapingClient() as client:
            for match in counting_matches:
                match_players = players_by_team.get(match.home_team_id, []) + players_by_team.get(
                    match.away_team_id, []
                )
                total_in_match = len(match_players)
                match_processed = 0
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

                    url = f"{base_url}/jugadores/{player.slug}"
                    try:
                        html = await client.fetch(url)
                    except ScrapingError as exc:
                        import httpx as _httpx

                        cause = exc.cause
                        is_not_found = (
                            isinstance(cause, _httpx.HTTPStatusError)
                            and cause.response.status_code == 404
                        )
                        is_server_error = (
                            isinstance(cause, _httpx.HTTPStatusError)
                            and cause.response.status_code >= 500
                        )
                        if is_not_found:
                            logger.info(
                                "scrape_matchday: player slug=%s not found (404), skipping",
                                player.slug,
                            )
                            total_skipped += 1
                            continue
                        if is_server_error:
                            # 5xx = remote server issue — treat as skip, don't block stats_ok
                            logger.warning(
                                "scrape_matchday: server error for player slug=%s: %s",
                                player.slug,
                                exc,
                            )
                            total_skipped += 1
                            team = team_names.get(player.team_id, "?")
                            error_details.append(self._format_scrape_error(player.name, team, exc))
                            continue
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

                    # Preserve historical position/match_id when the row already
                    # exists: a player may have changed position (winter draft)
                    # or team (real-life transfer) since the original scrape.
                    existing = await self.repo.get_player_stat(player.id, matchday_id)
                    if existing is not None:
                        position = existing.position
                        persisted_match_id = existing.match_id or match.id
                    else:
                        position = player.position
                        persisted_match_id = match.id

                    breakdown = engine.calculate(stats, position)

                    await self.repo.upsert_player_stat(
                        player_id=player.id,
                        matchday_id=matchday_id,
                        match_id=persisted_match_id,
                        position=position,
                        stats=stats,
                        breakdown=breakdown,
                    )
                    total_processed += 1
                    match_processed += 1

                # Mark stats_ok only when no errors AND at least one player
                # was actually processed (guards against marking ok when stats
                # are not yet available on the source site).
                if match_errors == 0 and match_processed > 0:
                    await self.repo.mark_match_stats_ok(match.id)
                    logger.info("scrape_matchday: marked match_id=%d stats_ok", match.id)

                    # Compute and store CRC for future change detection
                    if match.source_url:
                        try:
                            match_html = await client.fetch(match.source_url)
                            from src.features.scraping.parsers import parse_match_crc

                            crc = parse_match_crc(match_html)
                            await self.repo.update_match_crc(match.id, crc)
                        except Exception:
                            logger.warning(
                                "scrape_matchday: failed to compute CRC for match_id=%d",
                                match.id,
                            )
                elif match_errors > 0:
                    logger.warning(
                        "scrape_matchday: match_id=%d had %d errors, NOT marking stats_ok",
                        match.id,
                        match_errors,
                    )
                else:
                    logger.warning(
                        "scrape_matchday: match_id=%d — no stats found (all %d skipped), NOT marking stats_ok",
                        match.id,
                        total_in_match,
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
            from src.features.achievements.engine import AchievementEngine

            ach_engine = AchievementEngine(self.session)
            await ach_engine.evaluate_matchday(season_id, matchday_id, matchday_number)

        # Advance the season's scanned pointer when the matchday is fully done.
        if all_ok and counting_matches:
            await self.repo.update_season_matchday_scanned(season_id, matchday_number)

        # Advance matchday_current to next matchday when this one is complete.
        if all_ok and counting_matches and season and matchday_number == season.matchday_current:
            next_md = matchday_number + 1
            if next_md <= (season.matchday_end or 38):
                await self.repo.update_season_matchday_current(season_id, next_md)
                logger.info(
                    "scrape_matchday: advanced matchday_current %d -> %d",
                    matchday_number,
                    next_md,
                )

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
    ) -> dict[str, object]:
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
        log_repo = ScrapingLogRepository(self.session)

        def _make_log(pid: int | None, status: str, msg: str, detail: dict | None = None) -> dict:
            return {
                "season_id": season_id,
                "matchday_number": matchday_number,
                "match_id": match_id,
                "player_id": pid,
                "job_type": "match",
                "status": status,
                "message": msg,
                "detail": detail,
            }

        rules = await self.repo.get_scoring_rules(season_id)
        engine = ScoringEngine(rules)

        matchday = await self.repo.get_matchday(season_id, matchday_number)
        if matchday is None:
            msg = f"Jornada no encontrada: season={season_id} number={matchday_number}"
            scraping_log(_MANUAL, msg, "error")
            await log_repo.bulk_insert([_make_log(None, "error", msg)])
            return {"processed": 0, "skipped": 0, "errors": 1, "error_details": [msg]}

        matchday_id = matchday.id

        matches = await self.repo.get_matches_for_matchday(matchday_id)
        match = next((m for m in matches if m.id == match_id), None)
        if match is None:
            msg = f"Partido {match_id} no encontrado en J{matchday_number}"
            scraping_log(_MANUAL, msg, "error")
            await log_repo.bulk_insert([_make_log(None, "error", msg)])
            return {"processed": 0, "skipped": 0, "errors": 1, "error_details": [msg]}

        team_ids = {match.home_team_id, match.away_team_id}
        match_players = await self.repo.get_players_for_teams(season_id, team_ids)
        team_names = await self._team_names(team_ids)

        home_team = team_names.get(match.home_team_id, "?")
        away_team = team_names.get(match.away_team_id, "?")
        match_label = f"{home_team} vs {away_team}"
        scraping_log(
            _MANUAL,
            f"Match {match_id} ({match_label}) J{matchday_number}: "
            f"scrapeando {len(match_players)} jugadores",
        )

        total_processed = 0
        total_skipped = 0
        total_errors = 0
        error_details: list[str] = []

        base_url = self._settings.scraping_base_url

        async def _wlog(
            pid: int | None, status: str, msg: str, detail: dict | None = None
        ) -> None:
            """Write a single log entry committed immediately (visible to polling)."""
            await ScrapingLogRepository.write_log(_make_log(pid, status, msg, detail))

        await _wlog(None, "ok", f"Inicio: {match_label} — {len(match_players)} jugadores")

        try:
            async with ScrapingClient() as client:
                for player in match_players:
                    team = team_names.get(player.team_id, "?")
                    url = f"{base_url}/jugadores/{player.slug}"
                    try:
                        html = await client.fetch(url)
                    except ScrapingError as exc:
                        cause = exc.cause
                        is_not_found = (
                            isinstance(cause, httpx.HTTPStatusError)
                            and cause.response.status_code == 404
                        )
                        is_server_error = (
                            isinstance(cause, httpx.HTTPStatusError)
                            and cause.response.status_code >= 500
                        )
                        if is_not_found:
                            total_skipped += 1
                            await _wlog(player.id, "skip", f"{player.name} ({team}): 404")
                            continue
                        if is_server_error:
                            # 5xx = remote server issue, not our fault.
                            # Treat as skip so it doesn't block stats_ok.
                            total_skipped += 1
                            err_msg = f"{player.name} ({team}): {cause}"
                            error_details.append(err_msg)
                            await _wlog(player.id, "error", err_msg)
                            continue
                        total_errors += 1
                        err_msg = f"{player.name} ({team}): {cause}"
                        error_details.append(err_msg)
                        await _wlog(player.id, "error", err_msg)
                        continue

                    stats = parse_player_stats(html, matchday_number)
                    if stats is None:
                        total_skipped += 1
                        await _wlog(player.id, "skip", f"{player.name} ({team}): sin stats")
                        continue

                    # Preserve historical position/match_id when re-scraping.
                    existing = await self.repo.get_player_stat(player.id, matchday_id)
                    if existing is not None:
                        position = existing.position
                        persisted_match_id = existing.match_id or match_id
                    else:
                        position = player.position
                        persisted_match_id = match_id

                    breakdown = engine.calculate(stats, position)

                    await self.repo.upsert_player_stat(
                        player_id=player.id,
                        matchday_id=matchday_id,
                        match_id=persisted_match_id,
                        position=position,
                        stats=stats,
                        breakdown=breakdown,
                    )
                    total_processed += 1
                    await _wlog(
                        player.id,
                        "ok",
                        f"{player.name} ({team}): {breakdown.pts_total} pts",
                        {
                            "position": position,
                            "marca_rating": stats.marca_rating,
                            "as_picas": stats.as_picas,
                            "goals": stats.goals,
                            "assists": stats.assists,
                            "pts_total": breakdown.pts_total,
                        },
                    )
        except Exception as exc:
            err_msg = f"Error fatal: {exc}"
            await _wlog(None, "error", err_msg)
            total_errors += 1
            error_details.append(err_msg)

        await _wlog(
            None,
            "error" if total_errors > 0 else "ok",
            f"Fin: {total_processed} ok, {total_skipped} skip, {total_errors} error",
        )

        scraping_log(
            _MANUAL,
            f"Match {match_id} ({match_label}): "
            f"procesados={total_processed}, skipped={total_skipped}, errores={total_errors}",
            "error" if total_errors > 0 else "info",
        )

        if total_errors == 0 and total_processed > 0:
            await self.repo.mark_match_stats_ok(match_id)

            # Compute and store CRC so the scheduler can detect future changes
            if match.source_url:
                try:
                    async with ScrapingClient() as crc_client:
                        match_html = await crc_client.fetch(match.source_url)
                    from src.features.scraping.parsers import parse_match_crc

                    crc = parse_match_crc(match_html)
                    await self.repo.update_match_crc(match_id, crc)
                except Exception:
                    logger.warning(
                        "scrape_match_players: failed to compute CRC for match_id=%d",
                        match_id,
                    )
        elif total_processed == 0 and total_errors == 0:
            logger.warning(
                "scrape_match_players: match_id=%d — no stats found (all skipped), NOT marking stats_ok",
                match_id,
            )

        await self._aggregator.aggregate_matchday(matchday_id)

        # Check if all counting matches are now done → advance matchday.
        if total_errors == 0:
            refreshed = await self.repo.get_matches_for_matchday(matchday_id)
            counting = [m for m in refreshed if m.counts]
            all_ok = all(m.stats_ok for m in counting)
            if all_ok and counting:
                await self.repo.mark_matchday_stats_ok(matchday_id)
                await self.repo.update_matchday_status(matchday_id, "finished")

                season = await self.repo.get_season(season_id)
                if season and matchday_number == season.matchday_current:
                    next_md = matchday_number + 1
                    if next_md <= (season.matchday_end or 38):
                        await self.repo.update_season_matchday_current(season_id, next_md)
                        logger.info(
                            "scrape_match_players: advanced matchday_current %d -> %d",
                            matchday_number,
                            next_md,
                        )

                economy_svc = EconomyService(self.session)
                await economy_svc.generate_weekly_payments(season_id, matchday_id)
                from src.features.achievements.engine import AchievementEngine

                ach_engine = AchievementEngine(self.session)
                await ach_engine.evaluate_matchday(season_id, matchday_id, matchday_number)
                await self.repo.update_season_matchday_scanned(season_id, matchday_number)

        summary: dict[str, object] = {
            "processed": total_processed,
            "skipped": total_skipped,
            "errors": total_errors,
            "error_details": error_details,
        }
        logger.info("scrape_match_players: done — match_id=%d summary=%s", match_id, summary)
        return summary

    async def scrape_season_by_player(
        self,
        season_id: int,
        start: int | None = None,
        end: int | None = None,
    ) -> dict[str, object]:
        """Re-scrape a whole season by iterating players (one fetch per player).

        Compared to ``scrape_matchday`` looped N times, this performs N times
        fewer HTTP requests because each player's stats page contains all the
        matchdays in a single response.

        For each player:
        1. Fetch ``/jugadores/{slug}`` once.
        2. Parse every per-matchday row from the stats table.
        3. For each row in the [start, end] range that maps to a matchday in
           this season, upsert the player_stats row (match_id resolved via
           ``find_match_for_team(matchday_id, player.team_id)``).
        4. Rows for matchdays where the player's current team didn't play (or
           the player wasn't in that team yet) are skipped.

        After all players are processed, ``aggregate_matchday`` is called once
        per affected matchday so participant_matchday_scores stays consistent.
        """
        rules = await self.repo.get_scoring_rules(season_id)
        engine = ScoringEngine(rules)

        matchdays = await self.repo.get_matchdays_by_season(season_id, start=start, end=end)
        md_by_number = {md.number: md for md in matchdays}
        if not md_by_number:
            logger.warning(
                "scrape_season_by_player: no matchdays in range for season_id=%d", season_id
            )
            return {
                "players_processed": 0,
                "players_skipped": 0,
                "players_errors": 0,
                "rows_upserted": 0,
                "matchdays_aggregated": 0,
            }

        players = await self.repo.get_players_for_season(season_id)
        logger.info(
            "scrape_season_by_player: season_id=%d players=%d matchdays=%d (J%d-J%d)",
            season_id,
            len(players),
            len(md_by_number),
            min(md_by_number),
            max(md_by_number),
        )

        base_url = self._settings.scraping_base_url
        players_processed = 0
        players_skipped = 0
        players_errors = 0
        rows_upserted = 0
        affected_md_ids: set[int] = set()

        async with ScrapingClient() as client:
            for idx, player in enumerate(players, start=1):
                if not player.slug:
                    players_skipped += 1
                    continue

                url = f"{base_url}/jugadores/{player.slug}"
                try:
                    html = await client.fetch(url)
                except ScrapingError as exc:
                    cause = exc.cause
                    is_not_found = (
                        isinstance(cause, httpx.HTTPStatusError)
                        and cause.response.status_code == 404
                    )
                    if is_not_found:
                        players_skipped += 1
                        logger.debug(
                            "scrape_season_by_player: 404 for %s (slug=%s)",
                            player.name,
                            player.slug,
                        )
                        continue
                    players_errors += 1
                    logger.warning(
                        "scrape_season_by_player: fetch error for %s: %s",
                        player.name,
                        cause,
                    )
                    continue

                stats_list = parse_player_all_matchdays(html)
                if not stats_list:
                    players_skipped += 1
                    continue

                player_rows = 0
                for stats in stats_list:
                    md = md_by_number.get(stats.matchday_number)
                    if md is None:
                        continue

                    # Preserve historical position + match_id when re-scraping.
                    # A player who changed position (winter draft) or team
                    # (real transfer) must keep his old data for past matchdays.
                    existing = await self.repo.get_player_stat(player.id, md.id)
                    if existing is not None:
                        position = existing.position
                        match_id: int | None = existing.match_id
                    else:
                        position = player.position
                        match = await self.repo.find_match_for_team(md.id, player.team_id)
                        match_id = match.id if match else None

                    breakdown = engine.calculate(stats, position)
                    await self.repo.upsert_player_stat(
                        player_id=player.id,
                        matchday_id=md.id,
                        match_id=match_id,
                        position=position,
                        stats=stats,
                        breakdown=breakdown,
                    )
                    player_rows += 1
                    affected_md_ids.add(md.id)

                rows_upserted += player_rows
                players_processed += 1

                if idx % 25 == 0:
                    logger.info(
                        "scrape_season_by_player: progress %d/%d players "
                        "(processed=%d skipped=%d errors=%d rows=%d)",
                        idx,
                        len(players),
                        players_processed,
                        players_skipped,
                        players_errors,
                        rows_upserted,
                    )

        # Flush upserts so aggregator queries see the new rows.
        await self.session.flush()

        for md_id in sorted(affected_md_ids):
            await self._aggregator.aggregate_matchday(md_id)

        summary: dict[str, object] = {
            "players_processed": players_processed,
            "players_skipped": players_skipped,
            "players_errors": players_errors,
            "rows_upserted": rows_upserted,
            "matchdays_aggregated": len(affected_md_ids),
        }
        logger.info("scrape_season_by_player: done — %s", summary)
        return summary

    async def scrape_calendar(self, season_id: int) -> dict[str, int]:
        """Fetch the La Liga calendar and update match scores + dates in the DB.

        The year suffix is derived from the season ``name`` field
        (e.g. ``"2024-2025"`` → year ``"2025"``).

        Returns
        -------
        dict with keys ``scores_updated``, ``dates_updated`` and ``urls_updated``.
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
            return {"scores_updated": 0, "dates_updated": 0, "urls_updated": 0}

        season_year = _resolve_season_year(season)
        base_url = self._settings.scraping_base_url
        prefix = competition_url_prefix(season.kind, season.tournament_type)
        url = f"{base_url}/{prefix}/calendario/{season_year}"
        logger.info("scrape_calendar: fetching %s", url)

        async with ScrapingClient() as client:
            try:
                html = await client.fetch(url)
            except ScrapingError as exc:
                logger.error("scrape_calendar: fetch failed: %s", exc)
                return {"scores_updated": 0, "dates_updated": 0, "urls_updated": 0}

        calendar_matches = parse_calendar(html, season_year=season_year)
        logger.info("scrape_calendar: parsed %d matches from calendar", len(calendar_matches))

        scores_updated = 0
        dates_updated = 0

        urls_updated = 0
        for cal_match in calendar_matches:
            db_match = await self.repo.get_match_by_source_id(cal_match.source_id)
            if db_match is None:
                logger.debug(
                    "scrape_calendar: source_id=%d not in DB, skipping",
                    cal_match.source_id,
                )
                continue

            # Backfill source_url when futbolfantasy changes the URL format
            # (e.g. /partidos/{id} -> /partidos/{id}-{home}-{away}).
            new_source_url = _absolute_match_url(cal_match.source_url, base_url)
            if new_source_url and db_match.source_url != new_source_url:
                await self.repo.update_match_source_url(db_match.id, new_source_url)
                db_match.source_url = new_source_url
                urls_updated += 1

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
            "scrape_calendar: scores_updated=%d dates_updated=%d urls_updated=%d",
            scores_updated,
            dates_updated,
            urls_updated,
        )
        return {
            "scores_updated": scores_updated,
            "dates_updated": dates_updated,
            "urls_updated": urls_updated,
        }

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

    # ------------------------------------------------------------------
    # Season initialization: import teams, players, and calendar
    # ------------------------------------------------------------------

    _POSITION_MAP: ClassVar[dict[str, str]] = {
        "POR": "POR",
        "DEF": "DEF",
        "MED": "MID",
        "DEL": "DEL",
    }

    async def import_teams_and_players(self, season_id: int, season_slug: str) -> dict[str, int]:
        """Scrape teams from homepage, each team's roster, and the calendar.

        Creates Team, Player, and Match rows for the given season.
        Returns counts: ``{"teams": N, "players": M, "matches": K}``.
        """
        base_url = self._settings.scraping_base_url
        teams_created = 0
        players_created = 0
        matches_created = 0

        # Determine the homepage URL — Liga is the root, tournaments live
        # under their own section (e.g. /world-cup/home).
        season_for_url = await self.repo.get_season(season_id)
        if season_for_url is None:
            logger.error("import_teams_and_players: season_id=%d not found", season_id)
            return {"teams": 0, "players": 0, "matches": 0}
        if season_for_url.kind == "tournament":
            prefix_for_home = competition_url_prefix(
                season_for_url.kind, season_for_url.tournament_type
            )
            homepage_url = f"{base_url}/{prefix_for_home}/home"
        else:
            homepage_url = base_url

        async with ScrapingClient() as client:
            # 1. Fetch teams from homepage
            try:
                homepage_html = await client.fetch(homepage_url)
            except ScrapingError as exc:
                logger.error("import_teams_and_players: homepage fetch failed: %s", exc)
                return {"teams": 0, "players": 0, "matches": 0}

            team_data_list = parse_teams(homepage_html)
            logger.info("import_teams_and_players: parsed %d teams", len(team_data_list))

            # 2. Create Team rows and build lookup
            team_slug_to_id: dict[str, int] = {}
            team_name_to_id: dict[str, int] = {}
            for td in team_data_list:
                team = await self.repo.create_team(season_id=season_id, name=td.name, slug=td.slug)
                team_slug_to_id[td.slug] = team.id
                team_name_to_id[td.name] = team.id
                teams_created += 1

            await self.session.flush()

            # 3. Fetch each team's roster and create Player rows
            # URL patterns differ:
            #   Liga:       {base}/{team_slug}/{season_slug}
            #   Tournament: {base}/{prefix}/equipos/{team_slug}
            is_tournament = season_for_url.kind == "tournament"
            for td in team_data_list:
                team_id = team_slug_to_id[td.slug]
                if is_tournament:
                    prefix_for_roster = competition_url_prefix(
                        season_for_url.kind, season_for_url.tournament_type
                    )
                    roster_url = f"{base_url}/{prefix_for_roster}/equipos/{td.slug}"
                else:
                    roster_url = f"{base_url}/{td.slug}/{season_slug}"
                try:
                    roster_html = await client.fetch(roster_url)
                except ScrapingError as exc:
                    logger.warning(
                        "import_teams_and_players: roster fetch failed for %s: %s",
                        td.slug,
                        exc,
                    )
                    continue

                roster = parse_roster(roster_html)
                if not roster:
                    logger.info(
                        "import_teams_and_players: %s — no players found (squad probably not published yet)",
                        td.name,
                    )
                    continue
                for player_data in roster:
                    position = self._POSITION_MAP.get(player_data.position, player_data.position)
                    display_name = player_data.slug.replace("-", " ").title()
                    await self.repo.create_player(
                        season_id=season_id,
                        team_id=team_id,
                        name=display_name,
                        display_name=display_name,
                        slug=player_data.slug,
                        position=position,
                    )
                    players_created += 1

                logger.info("import_teams_and_players: %s → %d players", td.name, len(roster))

            await self.session.flush()

            # 4. Fetch calendar and create Match rows
            season = await self.repo.get_season(season_id)
            if season is None:
                logger.error("import_teams_and_players: season_id=%d not found", season_id)
                return {"teams": teams_created, "players": players_created, "matches": 0}

            season_year = _resolve_season_year(season)
            prefix = competition_url_prefix(season.kind, season.tournament_type)
            calendar_url = f"{base_url}/{prefix}/calendario/{season_year}"
            try:
                calendar_html = await client.fetch(calendar_url)
            except ScrapingError as exc:
                logger.error("import_teams_and_players: calendar fetch failed: %s", exc)
                return {"teams": teams_created, "players": players_created, "matches": 0}

        cal_matches = parse_calendar(calendar_html, season_year=season_year)
        logger.info("import_teams_and_players: parsed %d calendar matches", len(cal_matches))

        # Build matchday number → matchday_id lookup
        from sqlalchemy import select

        from src.shared.models.matchday import Matchday

        stmt = select(Matchday.id, Matchday.number).where(Matchday.season_id == season_id)
        result = await self.session.execute(stmt)
        md_number_to_id = {row.number: row.id for row in result.all()}

        for cal_match in cal_matches:
            matchday_id = md_number_to_id.get(cal_match.matchday_number)
            if matchday_id is None:
                continue

            home_id = team_name_to_id.get(cal_match.home_team_name)
            away_id = team_name_to_id.get(cal_match.away_team_name)
            if home_id is None or away_id is None:
                logger.debug(
                    "import_teams_and_players: team not found for match %s vs %s",
                    cal_match.home_team_name,
                    cal_match.away_team_name,
                )
                continue

            from datetime import datetime as _dt

            played_at = _dt.fromisoformat(cal_match.played_at) if cal_match.played_at else None

            source_url = _absolute_match_url(cal_match.source_url, base_url)

            await self.repo.create_match(
                matchday_id=matchday_id,
                home_team_id=home_id,
                away_team_id=away_id,
                source_id=cal_match.source_id,
                source_url=source_url,
                played_at=played_at,
            )
            matches_created += 1

        await self.session.flush()

        # Sync first_match_at from match dates
        if matches_created:
            await self.repo.sync_matchday_first_match_at(season_id)

        logger.info(
            "import_teams_and_players: done — teams=%d players=%d matches=%d",
            teams_created,
            players_created,
            matches_created,
        )
        return {"teams": teams_created, "players": players_created, "matches": matches_created}
