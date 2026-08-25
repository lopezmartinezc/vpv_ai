from __future__ import annotations

import logging
import unicodedata
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
    """A player entry extracted from a team's roster page.

    Note: ``position`` is empty (``""``) for tournament rosters scraped
    after the 2026-05 redesign — the position is no longer rendered in the
    team page and must be resolved per-player from the individual stats
    page via :func:`parse_player_position`.
    """

    slug: str  # e.g. "mbappe"
    position: str  # POR | DEF | MED | DEL, or "" when unknown
    team_name: str
    display_name: str = ""  # human-readable name from the anchor


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


def _strip_shirt_number(text: str) -> str:
    """Remove a leading shirt-number prefix from a roster name.

    futbolfantasy prefixes the shirt number to numbered players, e.g.
    ``"1. Antonio Sivera"`` or ``"25. Wojciech Szczesny"``; without this the
    number would be stored as part of the player's name. Names without a
    number ("Jesús Owono") are returned unchanged.
    """
    s = text.strip()
    i = 0
    while i < len(s) and s[i].isdigit():
        i += 1
    if 0 < i < len(s) and s[i] == ".":
        return s[i + 1 :].strip()
    return s


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
            # Display name: prefer alt (Liga), fall back to title (tournaments)
            name = str(anchor.get("alt", "")).strip() or str(anchor.get("title", "")).strip()
            href = str(anchor.get("href", "")).strip()
            # href is either relative ("/atletico-de-madrid") or absolute
            # ("https://.../world-cup/equipos/corea-del-sur"). Take the last
            # non-empty path segment as the slug.
            if href:
                segments = [s for s in href.rstrip("/").split("/") if s]
                slug = segments[-1] if segments else ""
            else:
                slug = ""
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


def parse_roster(html: str) -> list[PlayerUrlData]:
    """Extract player slugs from a team's roster page.

    Each player is rendered as an ``a.jugador`` anchor. The href may include
    a season suffix (e.g. ``/jugadores/lamine-yamal/world-cup-2026``); we
    keep only the slug — the season slug is stripped because individual
    stat pages live at ``/jugadores/{slug}`` regardless.

    The player's display name comes from the anchor's text. Position is
    NOT extracted here (the redesigned 2026 layout dropped the position
    sections) — callers resolve it from the player's own page via
    :func:`parse_player_position`.

    Returns an empty list on any parsing failure.
    """
    try:
        soup = _soup(html)

        team_name_tag = soup.find("span", class_="nombre")
        team_name = _tag_text(team_name_tag if isinstance(team_name_tag, Tag) else None)

        players: list[PlayerUrlData] = []
        seen_slugs: set[str] = set()

        for anchor in soup.find_all("a", class_="jugador"):
            if not isinstance(anchor, Tag):
                continue
            href = str(anchor.get("href", "")).strip()
            if "/jugadores/" not in href:
                continue
            after = href.split("/jugadores/", 1)[1].strip("/")
            if not after:
                continue
            slug = after.split("/", 1)[0]
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            display_name = _strip_shirt_number(_tag_text(anchor)) or slug.replace("-", " ").title()
            players.append(
                PlayerUrlData(
                    slug=slug,
                    position="",
                    team_name=team_name,
                    display_name=display_name,
                )
            )

        logger.debug("parse_roster: found %d players (team=%r)", len(players), team_name)
        return players

    except Exception:
        logger.exception("parse_roster: unexpected error")
        return []


_POSITION_BOX_TO_CODE: dict[str, str] = {
    "por": "POR",
    "def": "DEF",
    "med": "MED",
    "del": "DEL",
}

# Fallback for player pages without the rich stats panel: futbolfantasy
# shows the position in plain Spanish in a div.info-right (or similar).
# Keys lowercased + accent-free for matching via _norm().
_POSITION_LABEL_TO_CODE: dict[str, str] = {
    "portero": "POR",
    "defensa": "DEF",
    "defensa central": "DEF",
    "lateral": "DEF",
    "lateral derecho": "DEF",
    "lateral izquierdo": "DEF",
    "central": "DEF",
    "centrocampista": "MED",
    "mediocentro": "MED",
    "mediocampista": "MED",
    "mediapunta": "MED",
    "medio": "MED",
    "delantero": "DEL",
    "extremo": "DEL",
    "extremo derecho": "DEL",
    "extremo izquierdo": "DEL",
    "ariete": "DEL",
    "segundo delantero": "DEL",
}


def _norm_label(value: str) -> str:
    nfd = unicodedata.normalize("NFD", value)
    stripped = "".join(c for c in nfd if not unicodedata.combining(c))
    return stripped.lower().strip()


def parse_player_position(html: str) -> str | None:
    """Extract the player's position (POR/DEF/MED/DEL) from their stats page.

    Two-pass:
    1. Rich pages expose ``span.position-box`` whose CSS class includes
       the 3-letter code (``por``/``def``/``med``/``del``). This is the
       fast path for top players.
    2. Minimal pages (less famous players, recently added profiles) drop
       the stats panel entirely. Fall back to scanning the info table for
       a Spanish label like 'Mediocampista' / 'Defensa central' and map
       it to the canonical 3-letter code.

    Returns the code or ``None`` when neither source carries a position.
    """
    try:
        soup = _soup(html)

        # 1) Rich panel — fastest path.
        box = soup.find("span", class_="position-box")
        if isinstance(box, Tag):
            for cls in box.get("class") or []:
                code = _POSITION_BOX_TO_CODE.get(cls.lower())
                if code:
                    return code
            text = _tag_text(box).upper()
            if text in _POSITION_BOX_TO_CODE.values():
                return text

        # 2) Minimal page — scan the right-hand info column for a Spanish
        # label and map it. We pick the first matching label to avoid
        # accidental hits on body copy.
        for tag in soup.find_all(["div", "li", "span", "td"]):
            if not isinstance(tag, Tag):
                continue
            label = _norm_label(_tag_text(tag))
            if not label or len(label) > 30:
                continue
            code = _POSITION_LABEL_TO_CODE.get(label)
            if code:
                return code

        return None
    except Exception:
        logger.exception("parse_player_position: unexpected error")
        return None


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


def _matchday_number_from_fase(fase_text: str, knockout_final_matchday: int | None) -> int:
    """Map a calendar ``div.fase`` label to a matchday number.

    League fixtures label the round ``"Jornada N"`` whether played or
    not. Tournament knockout fixtures, however, only carry ``"Jornada N"``
    once they've been PLAYED — while pending they show the bracket-round
    notation instead: ``"1/16"`` (round of 32), ``"1/8"``, ``"1/4"``,
    ``"1/2"`` (semis) and ``"Final"`` / 3rd-place. Those map onto the tail
    matchdays counting back from the final::

        Final       -> knockout_final_matchday
        1/2 (semis) -> knockout_final_matchday - 1
        1/4         -> knockout_final_matchday - 2
        1/8         -> knockout_final_matchday - 3
        1/16        -> knockout_final_matchday - 4

    i.e. ``final - log2(denominator)``. ``knockout_final_matchday`` is
    ``None`` for leagues, so their labels never get coerced. Returns
    ``0`` when the label can't be resolved (caller skips such fixtures).
    """
    text = fase_text.strip()
    parts = text.split()
    # "Jornada 24" -> 24 (also tolerates any "<word> <int>" shape).
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass

    if knockout_final_matchday is None:
        return 0

    low = text.lower()
    # Final and 3rd/4th-place playoff both sit on the last matchday.
    if low == "final" or "puesto" in low or "tercer" in low:
        return knockout_final_matchday
    # "1/N" bracket notation, N a power of two.
    if text.startswith("1/"):
        try:
            denom = int(text[2:])
        except ValueError:
            return 0
        if denom >= 1 and (denom & (denom - 1)) == 0:  # power of two
            step = denom.bit_length() - 1  # log2(denom)
            md = knockout_final_matchday - step
            return md if md >= 1 else 0
    return 0


def parse_calendar(
    html: str,
    season_year: int = 0,
    knockout_final_matchday: int | None = None,
) -> list[CalendarMatchData]:
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

                # Matchday number — "Jornada 24" → 24, or a knockout
                # round label ("1/2", "Final") mapped back from the final.
                fase_div = anchor.find("div", class_="fase")
                fase_text = _tag_text(fase_div if isinstance(fase_div, Tag) else None)
                matchday_number = _matchday_number_from_fase(fase_text, knockout_final_matchday)

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


def _find_stats_table(html: str) -> Tag | None:
    """Locate the per-matchday stats table.

    Identified by a ``table.tablestats`` containing ``tr.plegado`` rows with a
    ``td.jorn-td`` cell. Historically this table lived inside ``div.puntos``;
    futbolfantasy's 2026 Vue redesign dropped that wrapper, so we scope to
    ``div.puntos`` when it's still present (back-compat) and otherwise search
    the whole document. The ``td.jorn-td`` shape filter uniquely identifies the
    per-matchday table either way (summary/top-scorer tables have no jorn-td).
    """
    soup = _soup(html)
    scopes: list[Tag] = []
    puntos_div = soup.find("div", class_="puntos")
    if isinstance(puntos_div, Tag):
        scopes.append(puntos_div)
    scopes.append(soup)  # fallback: wrapper removed in the Vue redesign
    for scope in scopes:
        for candidate in scope.find_all("table", class_="tablestats"):
            if isinstance(candidate, Tag) and candidate.find("td", class_="jorn-td") is not None:
                return candidate
    return None


def _build_stats_from_row(row: Tag, matchday_number: int) -> PlayerMatchdayStats:
    """Build a ``PlayerMatchdayStats`` from a ``tr.plegado`` row."""
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


def parse_player_stats(html: str, matchday_number: int) -> PlayerMatchdayStats | None:
    """Extract a player's stats for *matchday_number* from their stats page.

    Returns ``None`` when no per-matchday table is found, when the row for the
    requested matchday is absent, or on any parsing failure.
    """
    try:
        target_table = _find_stats_table(html)
        if target_table is None:
            logger.debug("parse_player_stats: no tablestats with jorn-td found")
            return None

        for row in target_table.find_all("tr", class_="plegado"):
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
            return _build_stats_from_row(row, matchday_number)

        logger.debug("parse_player_stats: matchday %d not found in table", matchday_number)
        return None

    except Exception:
        logger.exception("parse_player_stats: unexpected error for matchday=%d", matchday_number)
        return None


def parse_player_all_matchdays(html: str) -> list[PlayerMatchdayStats]:
    """Extract a player's stats for ALL matchdays present in the table.

    Useful for season-wide audits: a single HTTP fetch yields every matchday
    row instead of N fetches (one per matchday).

    Returns an empty list when no per-matchday table is found or on parsing
    failure.
    """
    try:
        target_table = _find_stats_table(html)
        if target_table is None:
            logger.debug("parse_player_all_matchdays: no tablestats with jorn-td found")
            return []

        out: list[PlayerMatchdayStats] = []
        for row in target_table.find_all("tr", class_="plegado"):
            if not isinstance(row, Tag):
                continue
            jorn_td = row.find("td", class_="jorn-td")
            if not isinstance(jorn_td, Tag):
                continue
            try:
                row_matchday = int(_tag_text(jorn_td))
            except ValueError:
                continue
            out.append(_build_stats_from_row(row, row_matchday))
        return out

    except Exception:
        logger.exception("parse_player_all_matchdays: unexpected error")
        return []


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

    The 2026 layout serves the photo as an ``<img>`` whose ``src`` matches
    one of two CDN paths:

    - ``.../uploads/images/jugadores/ficha/{id}.png`` — kit of the club
      (default on the bare ``/jugadores/{slug}`` page).
    - ``.../uploads/images/jugadores/ficha-seleccion/{id}.png`` — kit of
      the national team (used on the ``/jugadores/{slug}/world-cup-2026``
      style pages).

    Returns the first matching ``src``, or ``None`` if not present.
    """
    try:
        soup = _soup(html)
        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue
            src = str(img.get("src", "")).strip()
            if not src or "stats.png" in src:
                continue
            if "/jugadores/ficha/" in src or "/jugadores/ficha-seleccion/" in src:
                return src
        return None
    except Exception:
        logger.exception("parse_player_photo: unexpected error")
        return None


# ---------------------------------------------------------------------------
# Match page CRC — change detection for scheduler
# ---------------------------------------------------------------------------


def parse_match_score(html: str) -> tuple[int, int] | None:
    """Extract the match score from a match detail page.

    The match page on futbolfantasy uses two ``div.score`` elements at the top
    (one per team), each containing ``div.score-local`` and
    ``div.score-visitante``.  When not yet available, these contain ``"-"``.

    Falls back to ``div.resultado`` text and ``strong.score`` patterns.

    Returns ``(home_score, away_score)`` or ``None`` if not found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Primary: two sibling div.score elements at the top (home, away)
    score_divs = soup.find_all("div", class_="score")
    if len(score_divs) >= 2:
        home_text = score_divs[0].get_text(strip=True)
        away_text = score_divs[1].get_text(strip=True)
        if home_text.isdigit() and away_text.isdigit():
            return (int(home_text), int(away_text))

    # Alternative: single div.score with div.score-local + div.score-visitante children
    if len(score_divs) >= 1 and isinstance(score_divs[0], Tag):
        local = score_divs[0].find("div", class_="score-local")
        visit = score_divs[0].find("div", class_="score-visitante")
        if isinstance(local, Tag) and isinstance(visit, Tag):
            local_text = local.get_text(strip=True)
            visit_text = visit.get_text(strip=True)
            if local_text.isdigit() and visit_text.isdigit():
                return (int(local_text), int(visit_text))

    # Fallback: div.resultado with "N - N" text
    resultado = soup.find("div", class_="resultado")
    if isinstance(resultado, Tag):
        text = resultado.get_text(strip=True)
        if "-" in text:
            try:
                parts = text.split("-", 1)
                home = int(parts[0].strip())
                away = int(parts[1].strip())
                return (home, away)
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


# ---------------------------------------------------------------------------
# Parser: per-match player stats (for tournaments where the per-jornada
# player table doesn't exist — Mundial, Eurocopa, etc.)
#
# Configured via `seasons.tournament_config["stats_source"] = "match_page"`.
# The match page (https://www.futbolfantasy.com/partidos/{id}-...) is a
# single fetch that yields BOTH teams' rosters (~52 players) plus their
# raw stats, instead of N per-player fetches that fail anyway because
# tournament player pages lack the `jorn-td` markers we look for.
# ---------------------------------------------------------------------------


@dataclass
class MatchPagePlayer:
    """One player's stats extracted from a match page.

    `player_name_raw` keeps the surname as it appears on the page
    (e.g. "Montes 91'") so callers can both resolve the DB player
    and recover the sub-minute. `is_starter` reflects which section
    (Titulares vs Suplentes) the row sat under.

    `slug` is the futbolfantasy player slug pulled out of the desglose
    row's "Ver la ficha del jugador" link. It coincides with the
    ``players.slug`` column in our DB, so it's the safest match key —
    use it before falling back to ``surname_clean``, which can be a
    one-letter abbreviation ("Armando G.") when the page truncates
    long names.
    """

    team_name: str
    player_name_raw: str  # e.g. "Rangel" or "Montes 91'" or "Zwane 60' 83'"
    surname_clean: str  # surname only, lowercased, accents folded
    is_starter: bool
    stats: PlayerMatchdayStats
    slug: str | None = None


# Maps the Spanish stat names that appear in the desglose row to the
# PlayerMatchdayStats field they should fill. Values that don't map to
# any of our fields (sofascore-style metrics like "Pases clave") are
# intentionally absent — they're discarded.
#
# We deliberately do NOT map "Paradas" (total saves) to anything: VPV
# scoring only credits *penalty* saves, and the match page doesn't
# expose them distinctly from regular saves yet. When we see a real
# penalty save in production we'll add the detection (likely a new
# "Paradas de penalti" desglose entry, or an icon in td.events).
_DESGLOSE_STAT_TO_FIELD: dict[str, str] = {
    "Goles": "goals",
    "Asistencias": "assists",
    "Tiros al palo": "woodwork",
}


def _strip_accents_lower(value: str) -> str:
    """Lowercase + strip diacritics. Used to match scraped surnames to DB
    player names regardless of accents (Rangel vs Rangél, etc.)."""
    normalized = unicodedata.normalize("NFD", value)
    no_marks = "".join(c for c in normalized if not unicodedata.combining(c))
    return no_marks.lower().strip()


def _normalize_player_slug(slug: str) -> str:
    """Canonicalise a player slug to ascii-lower-hyphen form.

    futbolfantasy is inconsistent: some hrefs come URL-encoded
    (`Davinson-S%C3%A1nchez`), some preserve mixed case
    (`Davinson-Sánchez`), some are already lowercase ascii
    (`davinson-sanchez`). The roster scraper may have saved any of
    those into ``players.slug``, so we normalise on BOTH sides of the
    lookup — extract-time and roster-build-time — to the same
    canonical form: URL-decoded, NFD-stripped, lowercased.
    """
    from urllib.parse import unquote

    decoded = unquote(slug)
    normalized = unicodedata.normalize("NFD", decoded)
    no_marks = "".join(c for c in normalized if not unicodedata.combining(c))
    return no_marks.lower()


def _extract_player_slug(desglose_row: Tag) -> str | None:
    """Pull the futbolfantasy player slug from the desglose row.

    The desglose contains a "Ver la ficha del jugador" anchor with an
    href like ``/jugadores/armando-gonzalez/world-cup-2026``. That slug
    coincides with the ``players.slug`` column in our DB and is the
    safest match key — much better than the plegado row's text, which
    can truncate names ("Armando G." for "Armando González") and break
    the surname-based match.

    The regex tolerates URL-encoded chars (`%C3%A1`) and mixed case
    (`Davinson-Sánchez`); the result is run through
    ``_normalize_player_slug`` so the caller can compare against an
    equally-normalised roster slug.
    """
    import re as _re

    for a in desglose_row.find_all("a", href=True):
        href_raw = a.get("href")
        href = href_raw if isinstance(href_raw, str) else ""
        m = _re.search(r"/jugadores/([A-Za-z0-9%-]+)(?:/|$)", href)
        if m:
            return _normalize_player_slug(m.group(1))
    return None


def _surname_from_raw(name: str) -> tuple[str, list[int]]:
    """Split "Surname 65' 83'" into ("Surname", [65, 83]).

    The match page renders substitution minutes inline with the name
    (e.g. "Montes 91'", "Brian Gutiérrez 65'", "Zwane 60' 83'"). We
    keep BOTH the cleaned surname (for player matching) and the list
    of minutes (for inferring minutes_played later).
    """
    import re as _re

    minutes = [int(m) for m in _re.findall(r"(\d+)'", name)]
    # Strip every "NN'" token from the name, collapse whitespace, take
    # the LAST whitespace-separated token as the surname — matches both
    # "Rangel" and "Brian Gutiérrez" (we want "Gutiérrez").
    cleaned = _re.sub(r"\d+'", "", name).strip()
    if not cleaned:
        return ("", minutes)
    surname = cleaned.split()[-1]
    return (surname, minutes)


def _infer_minutes_played(is_starter: bool, minutes_in_name: list[int]) -> int:
    """Approximate minutes from the name's substitution markers.

    Starters with no marker → 90 (played the full game).
    Starters with a marker → subbed off at minute N → played N minutes.
    Subs with a marker → entered at minute N → played at least 90 - N
        minutes, with a floor of 1 (entries at minute 90+ still play
        the stoppage time, and Marca grades them "s/c" — they did
        play, so 0 would mis-classify them as "no jugó").
    Subs without a marker → never played → 0.
    """
    if is_starter:
        if not minutes_in_name:
            return 90
        return minutes_in_name[0]
    if not minutes_in_name:
        return 0
    return max(1, 90 - minutes_in_name[0])


def _events_flags(events_td: Tag | None) -> dict[str, bool | int]:
    """Read yellow / red / own-goal flags from the events column.

    The match page renders each event as an `<img alt="...">`. We look at
    the alt text rather than the icon URL because alt is stable across
    image-asset changes.
    """
    flags = {
        "yellow_card": False,
        "double_yellow": False,
        "red_card": False,
        "own_goals": 0,
    }
    if events_td is None:
        return flags
    yellow_count = 0
    for img in events_td.find_all("img"):
        alt = str(img.get("alt") or "").lower()
        if "roja" in alt:
            flags["red_card"] = True
        if "amarilla" in alt:
            yellow_count += 1
        # Only true own goals — NOT defensive errors that led to a goal.
        # futbolfantasy emits three related alts:
        #   "Gol en propia meta"                — autogol real (cuenta).
        #   "Error garrafal en gol"             — error que llevó a gol (NO autogol).
        #   "Error garrafal en gol en contra"   — error que llevó a gol del rival (NO autogol).
        # The old `"error" in alt and "gol en contra" in alt` test caught
        # the third one too, marking defensive errors as autogoles and
        # subtracting points incorrectly. Match the unambiguous phrase
        # "propia" (covers "meta" / "puerta" / future variants) instead.
        if "propia" in alt:
            assert isinstance(flags["own_goals"], int)
            flags["own_goals"] = flags["own_goals"] + 1
    if yellow_count == 1:
        flags["yellow_card"] = True
    elif yellow_count >= 2:
        flags["double_yellow"] = True
        flags["red_card"] = True  # double yellow ⇒ red, so the scoring engine sees both
    return flags


def _picas_count(picas_td: Tag | None) -> int:
    """The AS picas value is the count of `<img class="pica">` icons."""
    if picas_td is None:
        return 0
    return len(picas_td.find_all("img", class_="pica"))


def _parse_desglose_counts(desglose_row: Tag) -> dict[str, int]:
    """Pull raw stat counts from the first column of the desglose row.

    The desglose row has 12 `<div class="desg ...">` blocks, one per
    fantasy system. Raw COUNTS are identical across systems (only the
    points differ), so we read whichever block has the most stats
    (futbolfantasy-rpg is usually the richest).
    """
    import re as _re

    best_block: Tag | None = None
    best_count = -1
    for div in desglose_row.find_all("div", class_="desg"):
        stats_count = len(div.find_all("div", class_="estadistica"))
        if stats_count > best_count:
            best_count = stats_count
            best_block = div
    counts: dict[str, int] = {}
    if best_block is None:
        return counts
    for est in best_block.find_all("div", class_="estadistica"):
        text = est.get_text(" ", strip=True)
        # Forms we accept:
        #   "2  Paradas → 6 p"       → count=2 name="Paradas"
        #   "Portería a cero → 6 p"  → count=1 name="Portería a cero" (boolean event)
        #   "92%  Precisión pases → 4 p" → discarded (percent stats not in our model)
        m = _re.match(r"^(\d+)\s+(.+?)\s+(?:→\s+)?(-?[\d.]+)\s*p\s*$", text)
        if m:
            count = int(m.group(1))
            name = m.group(2).strip()
            counts[name] = count
            continue
        m_bool = _re.match(r"^([A-ZÁÉÍÓÚa-záéíóú][^\d]+?)\s+(?:→\s+)?(-?[\d.]+)\s*p\s*$", text)
        if m_bool:
            name = m_bool.group(1).strip()
            counts[name] = 1
    return counts


def _build_match_page_stats(
    *,
    matchday_number: int,
    is_starter: bool,
    minutes_played: int,
    sub_minute: int | None,
    home_score: int,
    away_score: int,
    is_home_player: bool,
    as_picas: str | None,
    marca_rating: str | None,
    event_flags: dict[str, bool | int],
    desglose_counts: dict[str, int],
) -> PlayerMatchdayStats:
    goals_for = home_score if is_home_player else away_score
    goals_against = away_score if is_home_player else home_score
    if goals_for > goals_against:
        result = 2
    elif goals_for == goals_against:
        result = 1
    else:
        result = 0

    # The match-page desglose row exposes every event the player-page
    # event icons cover. Read each penalty-related count the same way
    # we read goals — futbolfantasy uses both singular and plural
    # forms across pages, so try both when looking up.
    def _desg(*keys: str) -> int:
        for k in keys:
            if k in desglose_counts:
                return desglose_counts[k]
        return 0

    goals = _desg("Goles", "Gol")
    penalty_goals = _desg("Goles de penalti", "Gol de penalti")
    assists = _desg("Asistencias", "Asistencia")
    woodwork = _desg("Tiros al palo", "Tiro al palo")
    penalties_won = _desg("Penaltis forzados", "Penalti forzado")
    penalties_missed = _desg("Penaltis fallados", "Penalti fallado")
    penalties_committed = _desg("Penaltis cometidos", "Penalti cometido")
    # Penalty saves are NOT taken from "Paradas" — that's total saves,
    # and VPV scoring only credits penalty saves. The desglose row may
    # eventually expose them as their own entry; until we confirm the
    # exact key, leave at 0.
    penalties_saved = _desg("Penaltis parados", "Penalti parado")

    return PlayerMatchdayStats(
        matchday_number=matchday_number,
        played=minutes_played > 0,
        home_score=home_score,
        away_score=away_score,
        result=result,
        goals_for=goals_for,
        goals_against=goals_against,
        # event tells the ScoringEngine whether the player started:
        #   "Salida"  -> starter who was subbed off at sub_minute
        #   "Entrada" -> sub who came on at sub_minute (NOT a starter)
        #   None      -> starter who played the full 90 minutes
        # Without this, the engine treats every player with event=None
        # as a starter and awards the "Titular" bonus to subs who came
        # on (e.g. Christie 74' getting +1 starter pts wrongly).
        event=(
            "Salida"
            if (is_starter and sub_minute is not None)
            else "Entrada"
            if (not is_starter and sub_minute is not None)
            else None
        ),
        event_minute=sub_minute,
        minutes_played=minutes_played,
        goals=goals,
        penalty_goals=penalty_goals,
        assists=assists,
        penalties_saved=penalties_saved,
        woodwork=woodwork,
        penalties_won=penalties_won,
        penalties_missed=penalties_missed,
        own_goals=int(event_flags.get("own_goals") or 0),
        yellow_card=bool(event_flags.get("yellow_card")),
        yellow_removed=False,
        double_yellow=bool(event_flags.get("double_yellow")),
        red_card=bool(event_flags.get("red_card")),
        penalties_committed=penalties_committed,
        marca_rating=marca_rating,
        as_picas=as_picas,
    )


def _parse_match_score(soup: BeautifulSoup) -> tuple[int, int] | None:
    """Read the final score from a match page's `.resultado` block.

    Returns ``(home_score, away_score)`` or None when the score isn't
    yet published (early matchday).

    Preferred path: read `div.local.score` and `div.visitante.score`
    explicitly — futbolfantasy renders them inside `.resultado` for
    every published score. Fall back to a regex over the whole block
    only when the explicit divs aren't there (older layouts).
    """
    el = soup.find(class_="resultado")
    if not isinstance(el, Tag):
        return None

    def _node_int(node: Tag | None) -> int | None:
        if node is None:
            return None
        txt = node.get_text(strip=True)
        try:
            return int(txt)
        except ValueError:
            return None

    local = el.select_one("div.local.score")
    visitante = el.select_one("div.visitante.score")
    h = _node_int(local if isinstance(local, Tag) else None)
    a = _node_int(visitante if isinstance(visitante, Tag) else None)
    if h is not None and a is not None:
        return (h, a)

    # Fallback: scan integers in the block text. Lossy when team names
    # contain digits, but rescues older HTML where the explicit divs
    # weren't there.
    import re as _re

    nums = _re.findall(r"\b(\d+)\b", el.get_text(" ", strip=True))
    if len(nums) < 2:
        return None
    return (int(nums[0]), int(nums[1]))


def parse_match_page_players(
    html: str,
    *,
    matchday_number: int,
    home_team_name: str,
    away_team_name: str,
    fallback_score: tuple[int, int] | None = None,
) -> list[MatchPagePlayer]:
    """Parse all players' stats from a single match page.

    Matches by `class="tablestats"`: the first two are the per-player
    summary tables (home then away). Each table has a "Titulares" header
    followed by 11 player rows (paired plegado + desglose), then a
    "Suplentes" header and up to 15 sub rows.

    Returns one entry per player found, in document order. Players who
    didn't actually play (subs with no minute marker, 0 minutes
    inferred) are still returned so the caller can decide to skip them
    when persisting.

    ``fallback_score`` is used when the page's ``.resultado`` block
    doesn't expose the score (HTML hiccup, partial response, etc.).
    Callers should pass the matches-row score so we don't silently
    overwrite a known final score with the 0-0 default.
    """
    soup = _soup(html)
    score = _parse_match_score(soup)
    if score is None:
        if fallback_score is not None:
            logger.warning(
                "parse_match_page_players: no score on match page, using "
                "fallback %d-%d from caller (matches row)",
                fallback_score[0],
                fallback_score[1],
            )
            score = fallback_score
        else:
            logger.warning(
                "parse_match_page_players: no score found on match page, defaulting "
                "to 0-0 — result and imbatibilidad will be WRONG until re-scraped"
            )
            score = (0, 0)
    home_score, away_score = score

    tables = soup.find_all("table", class_="tablestats")
    # Defensive: page might have extra tablestats (desktop wide variants).
    # We want the two simple per-team tables that have plegado rows.
    per_team_tables = [t for t in tables if t.find("tr", class_="plegado")][:2]
    if len(per_team_tables) < 2:
        logger.warning(
            "parse_match_page_players: expected 2 per-team tablestats, found %d",
            len(per_team_tables),
        )
        return []

    out: list[MatchPagePlayer] = []
    for tbl_idx, tbl in enumerate(per_team_tables):
        team_name = home_team_name if tbl_idx == 0 else away_team_name
        is_home = tbl_idx == 0
        is_starter = True  # flips to False when we cross "Suplentes"
        rows = tbl.find_all("tr")
        for i, row in enumerate(rows):
            cls: list[str] = list(row.get("class") or [])
            text = row.get_text(" ", strip=True)
            if "header" in cls or ("Suplentes" in text and not cls):
                is_starter = False
                continue
            if "plegado" not in cls:
                continue
            name_td = row.find("td", class_="name")
            if not isinstance(name_td, Tag):
                continue
            raw_name = name_td.get_text(" ", strip=True)
            surname_raw, minutes_in_name = _surname_from_raw(raw_name)
            surname_clean = _strip_accents_lower(surname_raw)
            # Marca and AS-picas: keep the raw value the page renders.
            # "SC" (sin calificar) and "-" (mal calificado) ARE valid
            # ratings — they have their own scoring rules — so we
            # do NOT collapse them to None as an earlier version did.
            marca_rating = _parse_marca(row)
            as_picas = _parse_as_picas(row)
            event_flags = _events_flags(row.find("td", class_="events"))

            # The desglose row immediately follows the plegado row.
            desglose_row = rows[i + 1] if i + 1 < len(rows) else None
            desglose_counts: dict[str, int] = {}
            slug: str | None = None
            if isinstance(desglose_row, Tag) and "desglose" in (desglose_row.get("class") or []):
                desglose_counts = _parse_desglose_counts(desglose_row)
                slug = _extract_player_slug(desglose_row)

            minutes_played = _infer_minutes_played(is_starter, minutes_in_name)
            sub_minute = minutes_in_name[0] if minutes_in_name else None
            stats = _build_match_page_stats(
                matchday_number=matchday_number,
                is_starter=is_starter,
                minutes_played=minutes_played,
                sub_minute=sub_minute,
                home_score=home_score,
                away_score=away_score,
                is_home_player=is_home,
                as_picas=as_picas,
                marca_rating=marca_rating,
                event_flags=event_flags,
                desglose_counts=desglose_counts,
            )
            out.append(
                MatchPagePlayer(
                    team_name=team_name,
                    player_name_raw=raw_name,
                    surname_clean=surname_clean,
                    is_starter=is_starter,
                    stats=stats,
                    slug=slug,
                )
            )
    return out


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
