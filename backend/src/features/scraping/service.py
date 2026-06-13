from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from src.features.scraping.marca_image import ParsedMarcaRow
    from src.features.scraping.schemas_marca import (
        MarcaApplyRequest,
        MarcaPreviewResponse,
        MarcaRosterResponse,
    )

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.economy.service import EconomyService
from src.features.scraping.aggregation import ScoreAggregator
from src.features.scraping.client import ScrapingClient, ScrapingError
from src.features.scraping.config import (
    competition_url_prefix,
    scraping_settings,
    stats_source_for,
)
from src.features.scraping.log_buffer import scraping_log
from src.features.scraping.log_repository import ScrapingLogRepository
from src.features.scraping.parsers import (
    parse_calendar,
    parse_homepage_matchday,
    parse_match_page_players,
    parse_player_all_matchdays,
    parse_player_stats,
    parse_roster,
    parse_teams,
)
from src.features.scraping.repository import ScrapingRepository
from src.features.scraping.scoring import ScoringEngine
from src.shared.models.matchday import Match
from src.shared.models.player import Player
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

    async def _process_match_via_match_page(
        self,
        *,
        client: ScrapingClient,
        match: Match,
        matchday_id: int,
        matchday_number: int,
        engine: ScoringEngine,
        players_by_team: dict[int, list[Player]],
        team_names: dict[int, str],
    ) -> tuple[int, int, list[str]]:
        """Scrape one match by parsing the match page (Mundial/Eurocopa flow).

        Replaces N per-player fetches with a single fetch of
        ``match.source_url``. The page lists both teams' rosters (up to
        52 players) with raw stats. Players are matched to DB rows by
        team_id + accent-folded surname; entries with no surname match
        (e.g. a substitute who never made the season roster) are
        skipped silently.

        Returns ``(processed, errors, error_details)``.
        """
        import unicodedata as _ud

        source_url = match.source_url
        match_id = match.id
        home_team_id = match.home_team_id
        away_team_id = match.away_team_id

        home_team_name = team_names.get(home_team_id, "?")
        away_team_name = team_names.get(away_team_id, "?")

        if not source_url:
            msg = (
                f"match_id={match_id} sin source_url, no se puede scrapear "
                f"desde la página del partido"
            )
            logger.warning("scrape_matchday[match_page]: %s", msg)
            return (0, 1, [msg])

        logger.info(
            "scrape_matchday[match_page]: fetching match_id=%d url=%s",
            match_id,
            source_url,
        )
        try:
            html = await client.fetch(source_url)
        except ScrapingError as exc:
            msg = self._format_scrape_error(
                f"match {match_id}", f"{home_team_name} vs {away_team_name}", exc
            )
            logger.warning("scrape_matchday[match_page]: fetch failed: %s", msg)
            return (0, 1, [msg])

        try:
            parsed = parse_match_page_players(
                html,
                matchday_number=matchday_number,
                home_team_name=home_team_name,
                away_team_name=away_team_name,
            )
        except Exception as exc:
            logger.exception(
                "scrape_matchday[match_page]: parser failed for match_id=%d", match_id
            )
            return (0, 1, [f"match_id={match_id} parser error: {exc}"])

        if not parsed:
            msg = f"match_id={match_id} parser devolvió 0 jugadores (¿stats aún no publicadas?)"
            logger.info("scrape_matchday[match_page]: %s", msg)
            return (0, 0, [])

        # Build surname → Player lookups per team. The surname is the
        # LAST whitespace-separated token of `display_name`, lowercased
        # with diacritics stripped — keeps matching robust to encoding
        # variants ("Sánchez" vs "Sanchez").
        def _surname_key(name: str) -> str:
            n = _ud.normalize("NFD", name or "")
            n = "".join(c for c in n if not _ud.combining(c)).lower().strip()
            return n.split()[-1] if n else ""

        per_team_by_surname: dict[int, dict[str, Player]] = {}
        for team_id in (home_team_id, away_team_id):
            lookup: dict[str, Player] = {}
            for player in players_by_team.get(team_id, []):
                key = _surname_key(player.display_name)
                if key:
                    # Last write wins; surname collisions on the same
                    # team are rare and a tie-break heuristic isn't worth
                    # the complexity for v1.
                    lookup[key] = player
            per_team_by_surname[team_id] = lookup

        processed = 0
        errors = 0
        error_details: list[str] = []
        for mp in parsed:
            team_id = home_team_id if mp.team_name == home_team_name else away_team_id
            lookup = per_team_by_surname.get(team_id, {})
            matched: Player | None = lookup.get(mp.surname_clean)
            if matched is None:
                logger.debug(
                    "scrape_matchday[match_page]: surname=%s team_id=%d not in roster, skipping",
                    mp.surname_clean,
                    team_id,
                )
                continue
            if mp.stats.minutes_played == 0:
                # Bench player who didn't enter — no point in scoring.
                continue

            # Preserve historical position/match_id if we already have a
            # row for this player+matchday (mirrors the player-page flow).
            player_id = matched.id
            existing = await self.repo.get_player_stat(player_id, matchday_id)
            if existing is not None:
                position = existing.position
                persisted_match_id = existing.match_id or match_id
            else:
                position = matched.position
                persisted_match_id = match_id

            try:
                breakdown = engine.calculate(mp.stats, position)
            except Exception as exc:
                logger.exception(
                    "scrape_matchday[match_page]: scoring failed for player_id=%d", player_id
                )
                errors += 1
                error_details.append(f"{mp.player_name_raw} ({mp.team_name}): scoring error {exc}")
                continue

            await self.repo.upsert_player_stat(
                player_id=player_id,
                matchday_id=matchday_id,
                match_id=persisted_match_id,
                position=position,
                stats=mp.stats,
                breakdown=breakdown,
            )
            processed += 1

        logger.info(
            "scrape_matchday[match_page]: match_id=%d processed=%d errors=%d",
            match_id,
            processed,
            errors,
        )
        return (processed, errors, error_details)

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

        # Strategy per season: "player_page" (Liga default) hits each
        # player's individual stats page; "match_page" (Mundial etc.)
        # fetches the match page once and reads all 52 players at once.
        stats_source = stats_source_for(
            getattr(season, "tournament_config", None) if season else None
        )
        logger.info("scrape_matchday: season_id=%d stats_source=%s", season_id, stats_source)

        total_processed = 0
        total_skipped = 0
        total_errors = 0
        error_details: list[str] = []

        base_url = self._settings.scraping_base_url

        async with ScrapingClient() as client:
            for match in counting_matches:
                if stats_source == "match_page":
                    processed, errors, errs = await self._process_match_via_match_page(
                        client=client,
                        match=match,
                        matchday_id=matchday_id,
                        matchday_number=matchday_number,
                        engine=engine,
                        players_by_team=players_by_team,
                        team_names=team_names,
                    )
                    total_processed += processed
                    total_errors += errors
                    error_details.extend(errs)
                    if errors == 0 and processed > 0:
                        await self.repo.mark_match_stats_ok(match.id)
                        logger.info(
                            "scrape_matchday[match_page]: marked match_id=%d stats_ok",
                            match.id,
                        )
                    continue

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

        # Per-season strategy: tournaments configured with
        # tournament_config["stats_source"]="match_page" parse all 52
        # players from the match page itself instead of doing N
        # per-player fetches that don't work for tournaments anyway
        # (their player pages lack the per-jornada table).
        season_for_strategy = await self.repo.get_season(season_id)
        stats_source = stats_source_for(
            getattr(season_for_strategy, "tournament_config", None)
            if season_for_strategy
            else None
        )

        if stats_source == "match_page":
            scraping_log(
                _MANUAL,
                f"Match {match_id} ({match_label}) J{matchday_number}: "
                f"scrapeando vía página del partido (match_page)",
            )
            await ScrapingLogRepository.write_log(
                _make_log(None, "ok", f"Inicio [match_page]: {match_label}")
            )
            players_by_team: dict[int, list[Player]] = {}
            for player_row in match_players:
                players_by_team.setdefault(player_row.team_id, []).append(player_row)
            async with ScrapingClient() as client:
                processed, errors, errs = await self._process_match_via_match_page(
                    client=client,
                    match=match,
                    matchday_id=matchday_id,
                    matchday_number=matchday_number,
                    engine=engine,
                    players_by_team=players_by_team,
                    team_names=team_names,
                )
            if errors == 0 and processed > 0:
                await self.repo.mark_match_stats_ok(match_id)
                scraping_log(
                    _MANUAL,
                    f"Match {match_id} stats_ok marcado (procesados={processed})",
                )
            else:
                scraping_log(
                    _MANUAL,
                    f"Match {match_id} sin marcar stats_ok "
                    f"(procesados={processed}, errores={errors})",
                    "warning" if errors else "info",
                )
            await ScrapingLogRepository.write_log(
                _make_log(
                    None,
                    "ok" if errors == 0 else "warning",
                    f"Fin [match_page]: procesados={processed}, errores={errors}",
                )
            )
            return {
                "processed": processed,
                "skipped": 0,
                "errors": errors,
                "error_details": errs,
            }

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

    async def import_rosters_only(self, season_id: int) -> dict[str, int]:
        """Re-fetch every team's roster and create missing Player rows.

        Useful when the initial ``import_teams_and_players`` run created the
        Team rows but failed to populate players (e.g. because the
        ``parse_roster`` selector was broken at the time). Idempotent: a
        unique constraint on ``(season_id, slug)`` skips already-imported
        players via ``create_player``.

        Returns ``{"players_added": N, "teams_visited": M, "errors": K}``.
        """
        season = await self.repo.get_season(season_id)
        if season is None:
            return {"players_added": 0, "teams_visited": 0, "errors": 1}

        teams = await self.repo.get_teams_by_season(season_id)
        if not teams:
            logger.warning(
                "import_rosters_only: season_id=%d has no teams — run import first",
                season_id,
            )
            return {"players_added": 0, "teams_visited": 0, "errors": 0}

        # Skip slugs already present in DB to keep the command idempotent —
        # `players.uq_player_slug` would otherwise blow up on re-run.
        existing_slugs = set((await self.repo.get_players_by_slug(season_id)).keys())

        base_url = self._settings.scraping_base_url
        prefix = competition_url_prefix(season.kind, season.tournament_type)

        players_added = 0
        teams_visited = 0
        errors = 0

        async with ScrapingClient() as client:
            for team in teams:
                teams_visited += 1
                roster_url = f"{base_url}/{prefix}/equipos/{team.slug}/plantilla"
                try:
                    roster_html = await client.fetch(roster_url)
                except ScrapingError as exc:
                    logger.warning(
                        "import_rosters_only: roster fetch failed for %s: %s",
                        team.slug,
                        exc,
                    )
                    errors += 1
                    continue

                roster = parse_roster(roster_html)
                if not roster:
                    logger.info(
                        "import_rosters_only: %s — no players found (squad not published yet)",
                        team.name,
                    )
                    continue

                added_for_team = 0
                for player_data in roster:
                    if player_data.slug in existing_slugs:
                        continue
                    position = self._POSITION_MAP.get(player_data.position, player_data.position)
                    display_name = (
                        player_data.display_name or player_data.slug.replace("-", " ").title()
                    )
                    await self.repo.create_player(
                        season_id=season_id,
                        team_id=team.id,
                        name=display_name,
                        display_name=display_name,
                        slug=player_data.slug,
                        position=position,
                    )
                    existing_slugs.add(player_data.slug)
                    added_for_team += 1
                    players_added += 1

                logger.info(
                    "import_rosters_only: %s → +%d players (roster size=%d)",
                    team.name,
                    added_for_team,
                    len(roster),
                )

        await self.session.flush()
        return {
            "players_added": players_added,
            "teams_visited": teams_visited,
            "errors": errors,
        }

    async def sync_rosters(self, season_id: int) -> dict[str, int]:
        """Reconcile every team's roster against the live source.

        For each team in the season:
        - Fetch the current roster from
          ``{base}/{prefix}/equipos/{slug}/plantilla``.
        - Add any slug not yet in DB (same as ``import_rosters_only``).
        - Flip ``is_available=True`` for slugs that re-appear after being
          marked off-squad in a previous run.
        - Flip ``is_available=False`` for slugs that exist in DB but no
          longer appear in the roster (the player was cut from the official
          list).

        Soft-delete: the dropped players stay in DB so historical lineups
        and draft picks keep referring to them. The draft search and the
        predictions combobox already filter by ``is_available``.

        Returns ``{"players_added", "players_reactivated",
        "players_deactivated", "teams_visited", "teams_empty", "errors"}``.
        """
        season = await self.repo.get_season(season_id)
        if season is None:
            return {
                "players_added": 0,
                "players_reactivated": 0,
                "players_deactivated": 0,
                "teams_visited": 0,
                "teams_empty": 0,
                "errors": 1,
            }

        teams = await self.repo.get_teams_by_season(season_id)
        if not teams:
            logger.warning("sync_rosters: season_id=%d has no teams", season_id)
            return {
                "players_added": 0,
                "players_reactivated": 0,
                "players_deactivated": 0,
                "teams_visited": 0,
                "teams_empty": 0,
                "errors": 0,
            }

        base_url = self._settings.scraping_base_url
        prefix = competition_url_prefix(season.kind, season.tournament_type)

        players_added = 0
        players_reactivated = 0
        players_deactivated = 0
        teams_visited = 0
        teams_empty = 0
        errors = 0

        async with ScrapingClient() as client:
            for team in teams:
                teams_visited += 1
                roster_url = f"{base_url}/{prefix}/equipos/{team.slug}/plantilla"
                try:
                    roster_html = await client.fetch(roster_url)
                except ScrapingError as exc:
                    logger.warning("sync_rosters: roster fetch failed for %s: %s", team.slug, exc)
                    errors += 1
                    continue

                roster = parse_roster(roster_html)
                # Safety: if the scrape returns 0 players we treat it as "no
                # data available right now" rather than "everyone got cut",
                # otherwise a transient parser glitch would deactivate the
                # whole squad.
                if not roster:
                    logger.info("sync_rosters: %s — empty roster, skipping team", team.name)
                    teams_empty += 1
                    continue

                live_slugs = {pd.slug for pd in roster if pd.slug}
                db_players = await self.repo.get_players_by_team(team.id)
                db_by_slug = {p.slug: p for p in db_players if p.slug}

                # 1. Add brand-new slugs.
                added_for_team = 0
                for pd in roster:
                    if pd.slug in db_by_slug:
                        continue
                    display_name = pd.display_name or pd.slug.replace("-", " ").title()
                    position = self._POSITION_MAP.get(pd.position, pd.position)
                    await self.repo.create_player(
                        season_id=season_id,
                        team_id=team.id,
                        name=display_name,
                        display_name=display_name,
                        slug=pd.slug,
                        position=position,
                    )
                    added_for_team += 1
                    players_added += 1

                # 2. Re-activate any DB slug that came back into the roster.
                reactivate_ids = [
                    p.id for p in db_players if p.slug in live_slugs and not p.is_available
                ]
                players_reactivated += await self.repo.set_players_availability(
                    reactivate_ids, True
                )

                # 3. Soft-delete DB slugs no longer in the live roster.
                deactivate_ids = [
                    p.id for p in db_players if p.slug not in live_slugs and p.is_available
                ]
                players_deactivated += await self.repo.set_players_availability(
                    deactivate_ids, False
                )

                logger.info(
                    "sync_rosters: %s — added=%d, reactivated=%d, deactivated=%d (db=%d, live=%d)",
                    team.name,
                    added_for_team,
                    len(reactivate_ids),
                    len(deactivate_ids),
                    len(db_players),
                    len(live_slugs),
                )

        await self.session.flush()
        return {
            "players_added": players_added,
            "players_reactivated": players_reactivated,
            "players_deactivated": players_deactivated,
            "teams_visited": teams_visited,
            "teams_empty": teams_empty,
            "errors": errors,
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

            # 3. Fetch each team's roster and create Player rows.
            # Since the 2026-05 redesign, both Liga and tournaments use the
            # same URL pattern: {base}/{prefix}/equipos/{team_slug}/plantilla,
            # with the prefix coming from competition_url_prefix (laliga,
            # world-cup, eurocopa, ...). The trailing /plantilla is needed
            # — the bare /equipos/{slug} URL only renders a partial preview
            # (starters/most-known players); /plantilla returns the full
            # ~26-man roster. The roster page no longer exposes position;
            # players are created with position='' and the value is filled
            # later by PhotoDownloader, which fetches each player's own
            # page anyway to grab the photo.
            roster_prefix = competition_url_prefix(
                season_for_url.kind, season_for_url.tournament_type
            )
            for td in team_data_list:
                team_id = team_slug_to_id[td.slug]
                roster_url = f"{base_url}/{roster_prefix}/equipos/{td.slug}/plantilla"
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
                    display_name = (
                        player_data.display_name or player_data.slug.replace("-", " ").title()
                    )
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

    # ==================================================================
    # Marca rating (admin tool for tournaments where futbolfantasy
    # ships everyone as "SC").
    # ==================================================================

    async def marca_roster(self, match_id: int) -> MarcaRosterResponse:
        """Return both teams' rosters with their current marca_rating.

        Used by the Manual tab of /admin/marca to render an editable
        table without uploading an image. Players without a
        player_stats row yet appear with ``marca_rating=None`` and
        ``minutes_played=0`` so the admin can still classify them.
        """
        from src.features.scraping.schemas_marca import (
            MarcaPlayerRow,
            MarcaRosterResponse,
        )
        from src.shared.models.matchday import Match, Matchday
        from src.shared.models.player_stat import PlayerStat

        match = await self.session.get(Match, match_id)
        if match is None:
            from src.core.exceptions import NotFoundError

            raise NotFoundError("Match", match_id)
        matchday = await self.session.get(Matchday, match.matchday_id)
        if matchday is None:
            from src.core.exceptions import NotFoundError

            raise NotFoundError("Matchday", match.matchday_id)
        team_ids = {match.home_team_id, match.away_team_id}
        team_names = await self._team_names(team_ids)
        players = await self.repo.get_players_for_teams(matchday.season_id, team_ids)

        from sqlalchemy import select as sa_select

        stats_stmt = sa_select(PlayerStat).where(
            PlayerStat.matchday_id == match.matchday_id,
            PlayerStat.player_id.in_([p.id for p in players]),
        )
        stats_result = await self.session.execute(stats_stmt)
        stats_by_player: dict[int, PlayerStat] = {s.player_id: s for s in stats_result.scalars()}

        def _row(player: Player) -> MarcaPlayerRow:
            existing = stats_by_player.get(player.id)
            return MarcaPlayerRow(
                player_id=player.id,
                display_name=player.display_name,
                team_id=player.team_id,
                team_name=team_names.get(player.team_id, ""),
                marca_rating=existing.marca_rating if existing else None,
                minutes_played=existing.minutes_played if existing else 0,
                position=(existing.position if existing else player.position) or "",
            )

        home_rows = [_row(p) for p in players if p.team_id == match.home_team_id]
        away_rows = [_row(p) for p in players if p.team_id == match.away_team_id]
        # Primary: who PLAYED first (minutes_played > 0), then those
        # who didn't (0 mins) at the bottom — the admin only needs to
        # touch the top block. Secondary: position (POR → DEF → MED →
        # DEL → ""), then minutes desc, then name.
        pos_order = {"POR": 0, "DEF": 1, "MED": 2, "DEL": 3, "": 4}
        sort_key = lambda r: (  # noqa: E731
            r.minutes_played == 0,
            pos_order.get(r.position, 4),
            -r.minutes_played,
            r.display_name.lower(),
        )
        home_rows.sort(key=sort_key)
        away_rows.sort(key=sort_key)

        home_label = team_names.get(match.home_team_id, "?")
        away_label = team_names.get(match.away_team_id, "?")
        match_label = f"{home_label} vs {away_label}"

        return MarcaRosterResponse(
            match_id=match_id,
            match_label=match_label,
            matchday_number=matchday.number,
            home=home_rows,
            away=away_rows,
        )

    async def marca_apply(self, request: MarcaApplyRequest) -> dict[str, int]:
        """Persist marca_rating for each assignment, recompute pts and
        re-aggregate the matchday.
        """
        from src.core.exceptions import BusinessRuleError, NotFoundError
        from src.features.scraping.schemas_marca import VALID_MARCA_VALUES
        from src.shared.models.matchday import Match, Matchday

        match = await self.session.get(Match, request.match_id)
        if match is None:
            raise NotFoundError("Match", request.match_id)
        matchday = await self.session.get(Matchday, match.matchday_id)
        if matchday is None:
            raise NotFoundError("Matchday", match.matchday_id)
        rules = await self.repo.get_scoring_rules(matchday.season_id)
        engine = ScoringEngine(rules)

        updated = 0
        for a in request.assignments:
            # None == "no jugó" (NULL en BD, 0 pts). El resto debe ser
            # alguno de los seis strings que el ScoringEngine conoce.
            if a.marca_rating is not None and a.marca_rating not in VALID_MARCA_VALUES:
                raise BusinessRuleError(
                    f"marca_rating inválido para player_id={a.player_id}: {a.marca_rating!r}"
                )
            existing = await self.repo.get_player_stat(a.player_id, match.matchday_id)
            if existing is None:
                # No player_stats row yet — skip silently. The admin
                # can re-trigger after the next scrape populates it.
                logger.info(
                    "marca_apply: no player_stats row for player_id=%d matchday_id=%d, skipping",
                    a.player_id,
                    match.matchday_id,
                )
                continue
            old_marca_as = existing.pts_marca_as
            new_pts_marca = engine._calc_marca(a.marca_rating)
            new_pts_marca_as = new_pts_marca + existing.pts_as
            existing.marca_rating = a.marca_rating
            existing.pts_marca = new_pts_marca
            existing.pts_marca_as = new_pts_marca_as
            existing.pts_total = existing.pts_total - old_marca_as + new_pts_marca_as
            updated += 1

        await self.session.flush()
        if updated:
            await self._aggregator.aggregate_matchday(match.matchday_id)
        return {"updated": updated, "matchday_id": match.matchday_id}

    async def marca_preview(self, match_id: int, image_bytes: bytes) -> MarcaPreviewResponse:
        """OCR the cromo image and try to auto-match each row to a player.

        Returns the same ``MarcaPreviewResponse`` regardless of whether
        the image was readable: an empty result is a legitimate answer
        when Tesseract didn't find anything. The frontend renders the
        roster regardless so the admin can fall back to manual entry.
        """
        import unicodedata as _ud

        from src.features.scraping.marca_image import parse_marca_image
        from src.features.scraping.schemas_marca import (
            MarcaPreviewMatch,
            MarcaPreviewResponse,
            MarcaPreviewRow,
            MarcaPreviewUnmatched,
        )

        # Reuse the roster builder so the response is consistent
        # between the manual and image flows.
        roster_resp = await self.marca_roster(match_id)
        rows = parse_marca_image(image_bytes)

        # Build surname → MarcaPlayerRow lookup per team. Last write
        # wins on collisions (same logic as _process_match_via_match_page).
        def _surname_key(name: str) -> str:
            n = _ud.normalize("NFD", name or "")
            n = "".join(c for c in n if not _ud.combining(c)).lower().strip()
            return n.split()[-1] if n else ""

        all_roster = roster_resp.home + roster_resp.away
        by_surname: dict[str, list] = {}
        for player_row in all_roster:
            key = _surname_key(player_row.display_name)
            if key:
                by_surname.setdefault(key, []).append(player_row)

        # Multi-tier fuzzy: cuando no hay match exacto, puntuamos cada
        # apellido del roster por similitud y decidimos.
        #
        # Auto-match cuando:
        #   - score >= 0.85 (claramente cerca, p.ej. "Vasquez" vs "Vásquez")
        #   - score >= 0.65 Y hay margen >= 0.10 con el segundo mejor
        #     (resuelve "Ukon" → "Okon": 0.75 vs cero competidor)
        #
        # Si no, mandamos a `unmatched` pero con SOLO los top-5
        # candidatos ordenados por similitud — no la plantilla entera —
        # para que el admin elija de una shortlist relevante.
        import difflib

        roster_keys = list(by_surname.keys())

        def _rank_roster(query: str) -> list[tuple[str, float]]:
            """Return (key, score) for every roster key, sorted by score desc.

            Filter out scores below 0.55 — esos ya son ruido.
            """
            if not query:
                return []
            scored = [
                (key, difflib.SequenceMatcher(None, query, key).ratio()) for key in roster_keys
            ]
            scored = [(k, s) for k, s in scored if s >= 0.55]
            scored.sort(key=lambda x: -x[1])
            return scored

        stars_to_rating = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★"}

        def _resolve_rating(parsed_row: ParsedMarcaRow) -> str | None:
            """Marker priority: explicit textual marker → stars → null.

            Returns None when neither a marker nor a star was detected
            so the UI dropdown stays in the "no jugó" state.
            """
            if parsed_row.explicit_marker == "sc":
                return "SC"
            if parsed_row.explicit_marker == "dash":
                return "-"
            if parsed_row.stars > 0:
                return stars_to_rating[parsed_row.stars]
            return None

        matches: list[MarcaPreviewMatch] = []
        unmatched: list[MarcaPreviewUnmatched] = []
        for parsed in rows:
            preview_row = MarcaPreviewRow(
                surname_clean=parsed.surname_clean,
                stars=parsed.stars,
                is_substitute=parsed.is_substitute,
                minute=parsed.minute,
                raw_text=parsed.raw_text,
                confidence=parsed.confidence,
                explicit_marker=parsed.explicit_marker,
            )
            exact = by_surname.get(parsed.surname_clean, [])
            ranked = _rank_roster(parsed.surname_clean)

            # Decide whether we have a confident enough match to
            # auto-fill the dropdown.
            auto_match_key: str | None = None
            if len(exact) == 1:
                auto_match_key = parsed.surname_clean
            elif ranked:
                top_key, top_score = ranked[0]
                second_score = ranked[1][1] if len(ranked) > 1 else 0.0
                if top_score >= 0.85 or (top_score >= 0.65 and (top_score - second_score) >= 0.10):
                    auto_match_key = top_key

            if auto_match_key is not None and by_surname.get(auto_match_key):
                player = by_surname[auto_match_key][0]
                matches.append(
                    MarcaPreviewMatch(
                        row=preview_row,
                        player_id=player.player_id,
                        player_name=player.display_name,
                        marca_rating=_resolve_rating(parsed),
                    )
                )
                continue

            # Build a shortlist of the most plausible candidates so the
            # admin picks from a sorted dropdown of ≤5 names instead of
            # the full ~26-player roster.
            shortlist: list = []
            for key, _score in ranked:
                for player in by_surname.get(key, []):
                    shortlist.append(player)
                    if len(shortlist) >= 5:
                        break
                if len(shortlist) >= 5:
                    break
            if not shortlist:
                shortlist = all_roster
            unmatched.append(MarcaPreviewUnmatched(row=preview_row, candidates=shortlist))

        return MarcaPreviewResponse(
            match_id=match_id,
            match_label=roster_resp.match_label,
            matchday_number=roster_resp.matchday_number,
            roster=all_roster,
            matches=matches,
            unmatched=unmatched,
        )
