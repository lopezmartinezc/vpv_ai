from __future__ import annotations

import logging
import zlib
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclasses — pure data containers with no business logic
# ---------------------------------------------------------------------------


@dataclass
class TeamData:
    """A La Liga team as listed on futbolfantasy.com's navigation bar."""

    name: str
    slug: str  # e.g. "atletico-de-madrid" (leading slash stripped)


@dataclass
class PlayerUrlData:
    """A player entry extracted from a team's roster page."""

    slug: str  # e.g. "mbappe"
    position: str  # POR | DEF | MED | DEL
    team_name: str


@dataclass
class CalendarMatchData:
    """A single match entry from the La Liga calendar page."""

    source_id: int  # match ID as used by futbolfantasy
    source_url: str  # relative href, e.g. "/laliga/partido/12345-atletico-real-madrid"
    home_team_name: str
    away_team_name: str
    matchday_number: int
    result: str  # e.g. "2-1" or "" when not yet played
    played_at: str | None = None  # ISO datetime string, e.g. "2026-02-27T21:00:00"


@dataclass
class PlayerMatchdayStats:
    """Raw stats scraped from a player's individual stats page for one matchday."""

    matchday_number: int
    played: bool

    # Match result
    home_score: int
    away_score: int
    result: int  # 0=loss, 1=draw, 2=win  (from the player's team perspective)
    goals_for: int  # goals scored by the player's team
    goals_against: int  # goals conceded by the player's team

    # Participation
    event: str | None  # "Entrada" / "Salida" / None
    event_minute: int | None
    minutes_played: int  # 0 if didn't play

    # Positive events
    goals: int
    penalty_goals: int
    assists: int
    penalties_saved: int
    woodwork: int
    penalties_won: int

    # Negative events
    penalties_missed: int
    own_goals: int
    yellow_card: bool
    yellow_removed: bool
    double_yellow: bool
    red_card: bool
    penalties_committed: int

    # Media ratings (raw values, None if cell absent)
    marca_rating: str | None  # "★" .. "★★★★" | "-" | "SC"
    as_picas: str | None  # str(int) for count | "-" | "SC"


@dataclass
class HomepageMatchdayInfo:
    """Current matchday information extracted from the homepage."""

    matchday_number: int
    tab_id: str  # value of data-jornada attribute on the checked div
    ready_match_ids: list[int] = field(default_factory=list)  # IDs where stats are ready
    crc: str = ""  # hex-encoded CRC32 of the tab content string


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _tag_text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return tag.get_text(strip=True)


# ---------------------------------------------------------------------------
# Parser: teams from homepage
# ---------------------------------------------------------------------------


def parse_teams(html: str) -> list[TeamData]:
    """Extract team names and slugs from the homepage navigation bar.

    Looks for ``nav.cabecera`` > ``a.team`` elements.  Each anchor carries
    an ``alt`` attribute (display name) and an ``href`` like
    ``/atletico-de-madrid``.

    Returns an empty list on any parsing failure.
    """
    try:
        soup = _soup(html)
        cabecera = soup.find("nav", class_="cabecera")
        if not isinstance(cabecera, Tag):
            logger.warning("parse_teams: nav.cabecera not found")
            return []

        teams: list[TeamData] = []
        for anchor in cabecera.find_all("a", class_="team"):
            if not isinstance(anchor, Tag):
                continue
            name = str(anchor.get("alt", "")).strip()
            href = str(anchor.get("href", "")).strip()
            # href is like "/atletico-de-madrid" — strip leading slash for slug
            slug = href.lstrip("/")
            if name and slug:
                teams.append(TeamData(name=name, slug=slug))

        logger.debug("parse_teams: found %d teams", len(teams))
        return teams

    except Exception:
        logger.exception("parse_teams: unexpected error")
        return []


# ---------------------------------------------------------------------------
# Parser: player roster from a team page
# ---------------------------------------------------------------------------

_POSITION_SECTIONS: list[tuple[str, str]] = [
    ("porteros", "POR"),
    ("defensas", "DEF"),
    ("mediocampistas", "MED"),
    ("delanteros", "DEL"),
]


def parse_roster(html: str) -> list[PlayerUrlData]:
    """Extract player slugs and positions from a team's *plantilla* page.

    The page groups players in ``div.porteros``, ``div.defensas``,
    ``div.mediocampistas`` and ``div.delanteros``.  Each player is an
    ``a.jugador`` anchor with href like ``/jugadores/mbappe``.

    The team name is read from the first ``span.nombre``.

    Returns an empty list on any parsing failure.
    """
    try:
        soup = _soup(html)

        # Resolve team name
        team_name_tag = soup.find("span", class_="nombre")
        team_name = _tag_text(team_name_tag if isinstance(team_name_tag, Tag) else None)

        players: list[PlayerUrlData] = []
        for css_class, position in _POSITION_SECTIONS:
            section = soup.find("div", class_=css_class)
            if not isinstance(section, Tag):
                continue
            for anchor in section.find_all("a", class_="jugador"):
                if not isinstance(anchor, Tag):
                    continue
                href = str(anchor.get("href", "")).strip()
                # href is like "/jugadores/mbappe" — take last segment as slug
                slug = href.rstrip("/").split("/")[-1]
                if slug:
                    players.append(
                        PlayerUrlData(
                            slug=slug,
                            position=position,
                            team_name=team_name,
                        )
                    )

        logger.debug("parse_roster: found %d players (team=%r)", len(players), team_name)
        return players

    except Exception:
        logger.exception("parse_roster: unexpected error")
        return []


# ---------------------------------------------------------------------------
# Parser: La Liga calendar
# ---------------------------------------------------------------------------


def _parse_calendar_date(date_text: str, season_year: int) -> str | None:
    """Parse a calendar date string like ``'Vie 27/02 21:00h'`` into ISO format.

    The year is inferred from the season: months Aug-Dec belong to
    ``season_year - 1``; months Jan-Jul belong to ``season_year``.

    Times on futbolfantasy.com are in Spanish local time (Europe/Madrid),
    so the returned ISO string includes the correct UTC offset (CET +01:00
    or CEST +02:00 depending on DST).

    Returns an ISO datetime string or ``None`` on parse failure.
    """
    import re
    from zoneinfo import ZoneInfo

    m = re.search(r"(\d{2})/(\d{2})\s+(\d{2}):(\d{2})", date_text)
    if not m:
        return None

    day, month, hour, minute = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    year = season_year - 1 if month >= 8 else season_year

    try:
        from datetime import datetime as _dt

        madrid_tz = ZoneInfo("Europe/Madrid")
        dt = _dt(year, month, day, hour, minute, tzinfo=madrid_tz)
        return dt.isoformat()
    except ValueError:
        return None


def parse_calendar(html: str, season_year: int = 0) -> list[CalendarMatchData]:
    """Extract match data from the La Liga calendar page.

    Looks for ``section.lista`` > ``a.partido`` elements.  Each match
    anchor contains:

    - ``div.equipo.local img[alt]`` — home team name
    - ``div.equipo.visitante img[alt]`` — away team name
    - ``div.resultado`` (optional) — result string for completed matches
    - ``div.date`` (optional) — date/time for upcoming matches, e.g.
      ``"Vie 27/02 21:00h"``
    - ``div.fase`` — matchday label, e.g. ``"Jornada 24"``

    Parameters
    ----------
    html:
        Raw HTML of the calendar page.
    season_year:
        The second year of the season (e.g. 2026 for 2025-2026).
        Used to resolve ``dd/mm`` dates into full datetimes.

    Returns an empty list on any parsing failure.
    """
    try:
        soup = _soup(html)
        lista = soup.find("section", class_="lista")
        if not isinstance(lista, Tag):
            logger.warning("parse_calendar: section.lista not found")
            return []

        matches: list[CalendarMatchData] = []
        for anchor in lista.find_all("a", class_="partido"):
            if not isinstance(anchor, Tag):
                continue
            try:
                href = str(anchor.get("href", "")).strip()
                parts = [p for p in href.split("/") if p]
                if not parts:
                    logger.debug("parse_calendar: skipping empty href %r", href)
                    continue
                last_segment = parts[-1]
                id_candidate = last_segment.split("-")[0]
                if not id_candidate.isdigit():
                    logger.debug("parse_calendar: skipping malformed href %r", href)
                    continue
                source_id = int(id_candidate)

                # Home team — div.equipo.local > img[alt]
                local_div = anchor.find("div", class_="local")
                home_img = local_div.find("img") if isinstance(local_div, Tag) else None
                home_team = (
                    str(home_img.get("alt", "")).strip() if isinstance(home_img, Tag) else ""
                )

                # Away team — div.equipo.visitante > img[alt]
                visitante_div = anchor.find("div", class_="visitante")
                away_img = visitante_div.find("img") if isinstance(visitante_div, Tag) else None
                away_team = (
                    str(away_img.get("alt", "")).strip() if isinstance(away_img, Tag) else ""
                )

                # Result (completed matches only)
                resultado_div = anchor.find("div", class_="resultado")
                result = _tag_text(resultado_div if isinstance(resultado_div, Tag) else None)

                # Date/time (upcoming matches only — div.date inside div.info)
                played_at: str | None = None
                date_div = anchor.find("div", class_="date")
                if isinstance(date_div, Tag) and season_year:
                    date_text = date_div.get_text(" ", strip=True)
                    played_at = _parse_calendar_date(date_text, season_year)

                # Matchday number
                fase_div = anchor.find("div", class_="fase")
                fase_text = _tag_text(fase_div if isinstance(fase_div, Tag) else None)
                # "Jornada 24" → 24
                fase_parts = fase_text.split()
                matchday_number = int(fase_parts[1]) if len(fase_parts) >= 2 else 0

                matches.append(
                    CalendarMatchData(
                        source_id=source_id,
                        source_url=href,
                        home_team_name=home_team,
                        away_team_name=away_team,
                        matchday_number=matchday_number,
                        result=result,
                        played_at=played_at,
                    )
                )
            except (IndexError, ValueError):
                logger.debug("parse_calendar: skipping malformed match entry")
                continue

        logger.debug("parse_calendar: found %d matches", len(matches))
        return matches

    except Exception:
        logger.exception("parse_calendar: unexpected error")
        return []


# ---------------------------------------------------------------------------
# Parser: player stats for a single matchday
# ---------------------------------------------------------------------------


def _parse_score_and_result(
    row: Tag,
) -> tuple[int, int, int, int, int]:
    """Return (home_score, away_score, result, goals_for, goals_against).

    result: 2=win, 1=draw, 0=loss  (from the scraper perspective; the old
    code used 2/1/0 matching won/draw/lost class on the score strong tag).

    goals_for / goals_against are determined by the result:
    - won  → goals_for = max(scores), goals_against = min(scores)
    - lost → goals_for = min(scores), goals_against = max(scores)
    - draw → goals_for = goals_against = min(scores) (same value)
    """
    score_tag = row.find("strong", class_="score")
    score_text = _tag_text(score_tag if isinstance(score_tag, Tag) else None)
    raw_parts = score_text.split("-")
    try:
        left = int(raw_parts[0].strip())
        right = int(raw_parts[1].strip())
    except (IndexError, ValueError):
        left = right = 0

    home_score = left
    away_score = right
    max_g = max(left, right)
    min_g = min(left, right)

    if row.find("strong", class_="won"):
        result = 2
        goals_for = max_g
        goals_against = min_g
    elif row.find("strong", class_="lost"):
        result = 0
        goals_for = min_g
        goals_against = max_g
    else:  # draw (or no class found → fallback to draw)
        result = 1
        goals_for = min_g
        goals_against = min_g

    return home_score, away_score, result, goals_for, goals_against


def _parse_substitution(row: Tag) -> tuple[str | None, int | None, int]:
    """Return (event, event_minute, minutes_played).

    Reads ``span.cambio``.  If the span text is empty the player was a
    90-minute starter.  Otherwise the minute is extracted and the direction
    (Entrada/Salida) determines how many minutes the player played.
    """
    cambio_span = row.find("span", class_="cambio")
    if not isinstance(cambio_span, Tag):
        return None, None, 90

    cambio_text = cambio_span.get_text(strip=True)
    if not cambio_text:
        # Played the full 90 minutes as starter
        return None, None, 90

    # Extract minute — text is like "65'" so split on apostrophe
    minute_str = cambio_text.split("'")[0].strip()
    if not minute_str:
        return None, None, 90

    try:
        minute = int(minute_str)
    except ValueError:
        return None, None, 90

    # Determine direction
    if cambio_span.find("img", alt="Entrada") or cambio_span.find("img", alt="entrada"):
        return "Entrada", minute, 90 - minute
    if cambio_span.find("img", alt="Salida") or cambio_span.find("img", alt="salida"):
        return "Salida", minute, minute

    # Minute present but direction image missing — treat as starter subbed off
    return "Salida", minute, minute


def _parse_events(row: Tag) -> dict[str, int | bool]:
    """Count all event images inside ``td.events`` and return a mapping."""
    events_td = row.find("td", class_="events")
    if not isinstance(events_td, Tag):
        return {}

    def _count(alt: str) -> int:
        return len(events_td.find_all("img", alt=alt))

    return {
        "goals": _count("Gol"),
        "penalty_goals": _count("Gol de penalti"),
        "penalties_missed": _count("Penalti fallado"),
        "own_goals": _count("Gol en propia meta"),
        "assists": _count("Asistencia"),
        "penalties_saved": _count("Penalti parado"),
        "yellow_card": bool(_count("Amarilla")),
        "yellow_removed": bool(_count("Amarilla quitada por el comité")),
        "double_yellow": bool(_count("Doble amarilla")),
        "red_card": bool(_count("Roja directa")),
        "woodwork": _count("Tiro al palo"),
        "penalties_won": _count("Penaltis forzados"),
        "penalties_committed": _count("Penalti cometido"),
    }


def _parse_marca(row: Tag) -> str | None:
    """Return raw Marca rating string or None if cell is absent."""
    marca_td = row.find("td", class_="marca")
    if not isinstance(marca_td, Tag):
        return None
    return marca_td.get_text(strip=True) or None


def _parse_as_picas(row: Tag) -> str | None:
    """Return raw AS picas value or None if cell is absent.

    Counts ``img.pica`` elements.  Falls back to text content ("-" or "SC")
    when there are no pica images.
    """
    picas_td = row.find("td", class_="picas")
    if not isinstance(picas_td, Tag):
        return None

    pica_imgs = picas_td.find_all("img", class_="pica")
    if pica_imgs:
        return str(len(pica_imgs))

    text = picas_td.get_text(strip=True)
    return text if text else None


def parse_player_stats(html: str, matchday_number: int) -> PlayerMatchdayStats | None:
    """Extract a player's stats for *matchday_number* from their stats page.

    The stats table is at:
      3rd ``div.inside_tab`` (index 2)
        → 2nd ``table.tablestats`` (index 1)
          → all ``tr.plegado``

    Returns ``None`` when the row for the requested matchday is not found or
    on any parsing failure.
    """
    try:
        soup = _soup(html)

        inside_tabs = soup.find_all("div", class_="inside_tab")
        if len(inside_tabs) < 3:
            logger.debug(
                "parse_player_stats: expected 3+ inside_tab divs, found %d",
                len(inside_tabs),
            )
            return None

        stats_tab = inside_tabs[2]
        if not isinstance(stats_tab, Tag):
            return None

        tablestats = stats_tab.find_all("table", class_="tablestats")
        if len(tablestats) < 2:
            logger.debug(
                "parse_player_stats: expected 2+ tablestats, found %d",
                len(tablestats),
            )
            return None

        target_table = tablestats[1]
        if not isinstance(target_table, Tag):
            return None

        rows = target_table.find_all("tr", class_="plegado")

        for row in rows:
            if not isinstance(row, Tag):
                continue

            jorn_td = row.find("td", class_="jorn-td")
            if not isinstance(jorn_td, Tag):
                continue

            try:
                row_matchday = int(_tag_text(jorn_td))
            except ValueError:
                continue

            if row_matchday != matchday_number:
                continue

            # Found the matchday row — parse all fields
            played = row.find("span", class_="no-played-label") is None
            home_score, away_score, result, goals_for, goals_against = _parse_score_and_result(row)
            event, event_minute, minutes_played = _parse_substitution(row)
            events = _parse_events(row)
            marca_rating = _parse_marca(row)
            as_picas = _parse_as_picas(row)

            return PlayerMatchdayStats(
                matchday_number=matchday_number,
                played=played,
                home_score=home_score,
                away_score=away_score,
                result=result,
                goals_for=goals_for,
                goals_against=goals_against,
                event=event,
                event_minute=event_minute,
                minutes_played=minutes_played if played else 0,
                goals=int(events.get("goals", 0)),
                penalty_goals=int(events.get("penalty_goals", 0)),
                penalties_missed=int(events.get("penalties_missed", 0)),
                own_goals=int(events.get("own_goals", 0)),
                assists=int(events.get("assists", 0)),
                penalties_saved=int(events.get("penalties_saved", 0)),
                yellow_card=bool(events.get("yellow_card", False)),
                yellow_removed=bool(events.get("yellow_removed", False)),
                double_yellow=bool(events.get("double_yellow", False)),
                red_card=bool(events.get("red_card", False)),
                woodwork=int(events.get("woodwork", 0)),
                penalties_won=int(events.get("penalties_won", 0)),
                penalties_committed=int(events.get("penalties_committed", 0)),
                marca_rating=marca_rating,
                as_picas=as_picas,
            )

        logger.debug("parse_player_stats: matchday %d not found in table", matchday_number)
        return None

    except Exception:
        logger.exception("parse_player_stats: unexpected error for matchday=%d", matchday_number)
        return None


# ---------------------------------------------------------------------------
# Parser: homepage matchday info + CRC change detection
# ---------------------------------------------------------------------------


def parse_homepage_matchday(html: str) -> HomepageMatchdayInfo | None:
    """Extract current matchday info and CRC from the homepage.

    Logic (mirrors comprobar_jornada.py from the legacy scraper):
    1. Find ``div.tabs`` > ``div.checked`` to get the current jornada number
       and ``data-jornada`` tab ID.
    2. Collect all ``div.jornada{tab_id}`` divs.
    3. For each, accumulate text + canal image ``data-src`` values into a CRC
       string.
    4. A match is "ready" (stats available) when its div has both a
       ``picaroja`` AND ``estrella`` canal image.
    5. CRC is the zlib.crc32 of the accumulated string, formatted as a
       decimal string to match the legacy file format.

    Returns ``None`` on any parsing failure.
    """
    try:
        soup = _soup(html)

        tabs_div = soup.find("div", class_="tabs")
        if not isinstance(tabs_div, Tag):
            logger.warning("parse_homepage_matchday: div.tabs not found")
            return None

        checked_div = tabs_div.find("div", class_="checked")
        if not isinstance(checked_div, Tag):
            logger.warning("parse_homepage_matchday: div.checked not found")
            return None

        tab_id = str(checked_div.get("data-jornada", "1")).strip()

        # Extract matchday number from text like "J24" or "Jornada 24"
        chk_text = checked_div.get_text(strip=True)
        matchday_number = 0
        if "J" in chk_text:
            after_j = chk_text.split("J", 1)[1]
            # Could be "ornada 24" or just "24"
            digits = "".join(ch for ch in after_j if ch.isdigit())
            if digits:
                matchday_number = int(digits[:2])  # cap to 2 digits (38 jornadas)

        # Verify the tab actually has a canal image (used in legacy code as a
        # precondition before computing CRC)
        first_img = checked_div.find("img")
        if not isinstance(first_img, Tag) or not first_img.get("data-src"):
            logger.debug("parse_homepage_matchday: checked div has no canal img")
            return HomepageMatchdayInfo(
                matchday_number=matchday_number,
                tab_id=tab_id,
                ready_match_ids=[],
                crc="",
            )

        # Build the jornada divs — class contains "jornada{tab_id}"
        target_class = f"jornada{tab_id}"
        jornada_divs = soup.find_all(
            "div", class_=lambda c: c is not None and target_class in c.split()
        )

        crc_string = ""
        ready_match_ids: list[int] = []

        for part in jornada_divs:
            if not isinstance(part, Tag):
                continue

            crc_string += part.get_text(strip=True)

            partido_anchor = part.find("a", class_="partido")
            if not isinstance(partido_anchor, Tag):
                continue
            href = str(partido_anchor.get("href", ""))
            # Extract the match ID from the last non-empty path segment,
            # before the first dash.  Supports URLs with or without a season
            # sub-path (e.g. /laliga/partido/12345-slug or
            # /laliga/partido/2024-25/12345-slug).
            href_non_empty = [p for p in href.split("/") if p]
            if not href_non_empty:
                continue
            id_str = href_non_empty[-1].split("-")[0]
            if not id_str.isdigit():
                continue
            match_id = int(id_str)

            has_picaroja = False
            has_estrella = False
            for canal_img in part.find_all("img", class_="canal"):
                if not isinstance(canal_img, Tag):
                    continue
                data_src = str(canal_img.get("data-src", ""))
                crc_string += data_src
                if "picaroja" in data_src:
                    has_picaroja = True
                if "estrella" in data_src:
                    has_estrella = True

            if has_picaroja and has_estrella:
                ready_match_ids.append(match_id)

        crc_value = str(zlib.crc32(crc_string.encode("utf-8")))

        return HomepageMatchdayInfo(
            matchday_number=matchday_number,
            tab_id=tab_id,
            ready_match_ids=ready_match_ids,
            crc=crc_value,
        )

    except Exception:
        logger.exception("parse_homepage_matchday: unexpected error")
        return None


# ---------------------------------------------------------------------------
# Player photo
# ---------------------------------------------------------------------------


def parse_player_photo(html: str) -> str | None:
    """Extract the player's profile photo URL from their stats page.

    Looks for the first ``<img>`` inside ``div.profile``.  Returns the
    ``src`` attribute value or ``None`` if not found.
    """
    soup = BeautifulSoup(html, "lxml")
    profile_div = soup.select_one("div.profile")
    if profile_div is None:
        return None
    img = profile_div.find("img")
    if not isinstance(img, Tag):
        return None
    src = str(img.get("src", "")).strip()
    return src if src else None


# ---------------------------------------------------------------------------
# Match page CRC — change detection for scheduler
# ---------------------------------------------------------------------------


def parse_match_score(html: str) -> tuple[int, int] | None:
    """Extract the match score from a match detail page.

    Looks for ``div.resultado`` containing two ``span`` elements with the
    home and away scores.  Falls back to ``strong.score`` text like ``"2-1"``.

    Returns ``(home_score, away_score)`` or ``None`` if not found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Try div.resultado with score spans
    resultado = soup.find("div", class_="resultado")
    if isinstance(resultado, Tag):
        spans = resultado.find_all("span")
        if len(spans) >= 2:
            try:
                home = int(spans[0].get_text(strip=True))
                away = int(spans[1].get_text(strip=True))
                return (home, away)
            except (ValueError, IndexError):
                pass
        # Try text like "2 - 1" directly in resultado
        text = resultado.get_text(strip=True)
        if "-" in text:
            try:
                parts = text.split("-", 1)
                return (int(parts[0].strip()), int(parts[1].strip()))
            except (ValueError, IndexError):
                pass

    # Fallback: strong.score like in player stats rows
    score_tag = soup.find("strong", class_="score")
    if isinstance(score_tag, Tag):
        text = score_tag.get_text(strip=True)
        if "-" in text:
            try:
                parts = text.split("-", 1)
                return (int(parts[0].strip()), int(parts[1].strip()))
            except (ValueError, IndexError):
                pass

    return None


def parse_match_crc(html: str) -> str:
    """Compute a CRC from the match page's player ratings.

    Extracts all ``span[data-juego="modo-picas"]`` and
    ``span[data-juego="cronistas-marca"]`` text values from the match page
    (e.g. ``/partidos/20313-athletic-elche``), concatenates them, and returns
    a CRC32 string.  A change in the CRC indicates that player ratings have
    been updated on futbolfantasy.com and a re-scrape is warranted.
    """
    soup = BeautifulSoup(html, "lxml")
    parts: list[str] = []
    for juego in ("modo-picas", "cronistas-marca"):
        for span in soup.find_all("span", attrs={"data-juego": juego}):
            parts.append(span.get_text(strip=True))
    crc_string = "|".join(parts)
    return str(zlib.crc32(crc_string.encode("utf-8")))
