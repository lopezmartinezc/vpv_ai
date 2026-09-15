"""Parsers for the probable-lineup pages of futbolfantasy and analiticafantasy.

Pure functions over HTML. When a page changes shape they return what they can —
usually nothing — and log it; they never raise. A redesign has to leave the
lineup screen saying "no data from futbolfantasy", not break the refresh (the
2026 futbolfantasy redesign once took the stats parser down to 4 of 849).

futbolfantasy, team page ``/laliga/equipos/{slug}``: the probable eleven sits
in ``div.jugadores-titulares-{match}`` and the rest in ``.suplentes-container``.
Every player is an ``a.camiseta`` whose ``href`` ends in the player's slug —
the same slug as ours — with ``data-probabilidad="60%"``; rotation and
cautions are icons inside it. Injuries, doubts and suspensions are listed apart,
in "Estado físico de la plantilla" (``section.lesionados``) and
``section.sancionados``, with the medical report.

analiticafantasy, match page ``/partido/{id}-…``: the page is a Next.js app and
ships its data in ``self.__next_f.push([1, "…"])`` chunks. Joined and decoded,
they contain ``"lineupBlock": {"home": …, "away": …}`` with every player's
``chance``, ``esTitular`` and ``playerExtras`` (injury, doubt, sanction), and
the team names in ``"homeTeam"`` / ``"awayTeam"``. Reading that JSON is far
sturdier than scraping Tailwind class names.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

MADRID = ZoneInfo("Europe/Madrid")

# Worst first: when a player carries several states, the gravest one wins.
STATUS_PRECEDENCE = ("sancionado", "no_disponible", "lesionado", "duda", "rotacion", "apercibido")

_FF_ICONS = {
    "sancionado": "sancionado",
    "lesionado": "lesionado",
    "nodisponible": "no_disponible",
    "duda": "duda",
    "rotacion": "rotacion",
    "apercibido": "apercibido",
    # Back from injury: listed with the injured, but available.
    "disponible": "disponible",
}

_AF_POSITIONS = {0: "POR", 1: "DEF", 2: "MED", 3: "DEL"}


@dataclass(frozen=True)
class SourcePlayer:
    name: str
    probability: int | None
    starter: bool
    status: str | None = None
    note: str | None = None
    # The source's own slug. futbolfantasy's is ours; analiticafantasy's is not.
    slug: str | None = None
    position: str | None = None


@dataclass(frozen=True)
class SourceNews:
    title: str
    url: str
    published_at: datetime | None


@dataclass(frozen=True)
class SourceTeam:
    name: str
    players: list[SourcePlayer] = field(default_factory=list)
    formation: str | None = None


def _percent(value: object) -> int | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return max(0, min(100, int(value)))
    match = re.search(r"(\d{1,3})\s*%?", str(value or ""))
    return max(0, min(100, int(match.group(1)))) if match else None


def _gravest(statuses: set[str]) -> str | None:
    return next((s for s in STATUS_PRECEDENCE if s in statuses), None)


# --- futbolfantasy ---------------------------------------------------------------


def _ff_slug(href: str) -> str | None:
    match = re.search(r"/jugadores/([a-z0-9-]+)", href or "")
    return match.group(1) if match else None


def _ff_icons(tag: Tag) -> set[str]:
    found: set[str] = set()
    for img in tag.find_all("img"):
        name = str(img.get("src") or "").rsplit("/", 1)[-1].lower()
        for key, status in _FF_ICONS.items():
            if name.startswith(key):
                found.add(status)
    return found


def _ff_status(anchor: Tag) -> str | None:
    found = _ff_icons(anchor)
    if (anchor.get("data-nodisponible") or "0") not in ("0", ""):
        found.add("no_disponible")
    return _gravest(found)


def _ff_name(block: Tag, slug: str | None) -> str:
    """The name printed under the shirt, or the slug spelled out.

    The label reads "Bernal 7 7 5 … 23,37M … 19 años … Rotación": the name is
    what comes before the first number.
    """
    link = block.select_one("div.juggadores a.juggador")
    if link is not None:
        text = " ".join(link.get_text(" ", strip=True).split())
        name = re.split(r"\s+(?=[-+]?\d)", text, maxsplit=1)[0].strip()
        if name:
            return name
    return (slug or "").replace("-", " ").title()


def _clean_report(text: str) -> str:
    """Drop the link labels ("Noticia", "Parte médico") that close a report."""
    return re.sub(r"(\s*\b(?:Noticia|Parte m[eé]dico)\b)+\s*$", "", text).strip()


def _ff_absences(soup: BeautifulSoup) -> dict[str, tuple[str | None, str | None, str]]:
    """slug → (status, report, name) from "Estado físico de la plantilla" and
    the suspensions. A player back from injury is listed there too, with the
    "disponible" icon: he keeps his report and no state."""
    absences: dict[str, tuple[str | None, str | None, str]] = {}
    for selector, default in (
        ("section.lesionados", "lesionado"),
        ("section.sancionados", "sancionado"),
    ):
        for item in soup.select(f"{selector} div.elemento"):
            links = item.select("a[href*='/jugadores/']")
            named = next((a for a in links if a.get_text(strip=True)), None)
            anchor = named or (links[0] if links else None)
            slug = _ff_slug(str(anchor.get("href") or "")) if anchor is not None else None
            if not slug:
                continue
            name = " ".join(named.get_text(" ", strip=True).split()) if named is not None else ""
            text = " ".join(item.get_text(" ", strip=True).split())
            report = _clean_report(text[len(name) :] if name and text.startswith(name) else text)
            icons = _ff_icons(item)
            status = _gravest(icons) or (None if "disponible" in icons else default)
            absences[slug] = (status, report or None, name or slug.replace("-", " ").title())
    return absences


def _ff_news_date(text: str, now: datetime) -> datetime | None:
    """ "15/09 03:32" carries no year: take the one that is not in the future."""
    match = re.match(r"\s*(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    day, month, hour, minute = (int(g) for g in match.groups())
    try:
        dated = datetime(now.year, month, day, hour, minute, tzinfo=MADRID)
        # A date more than a day ahead belongs to last year (news from December
        # read in January).
        if (dated - now).total_seconds() > 86_400:
            dated = dated.replace(year=now.year - 1)
    except ValueError:
        return None
    return dated


def _ff_lineup(soup: BeautifulSoup) -> list[SourcePlayer]:
    players: list[SourcePlayer] = []
    seen: set[str] = set()
    sections = [
        (soup.select_one("div[class*='jugadores-titulares-']"), True),
        (soup.select_one("div.suplentes-container"), False),
    ]
    for section, starter in sections:
        if section is None:
            continue
        for block in section.select("div.tipo_campo"):
            anchor = block.select_one("a.camiseta")
            if anchor is None:
                continue
            # No page of his own on futbolfantasy: href="#". He is kept by his
            # printed name, to be matched by name.
            slug = _ff_slug(str(anchor.get("href") or ""))
            name = _ff_name(block, slug)
            key = slug or name
            if not key or key in seen:
                continue
            seen.add(key)
            players.append(
                SourcePlayer(
                    name=name,
                    probability=_percent(anchor.get("data-probabilidad")),
                    starter=starter,
                    status=_ff_status(anchor),
                    slug=slug,
                )
            )
    return players


def _ff_news(soup: BeautifulSoup, now: datetime) -> list[SourceNews]:
    news: list[SourceNews] = []
    for link in soup.select("section.news a[href*='/noticias/']"):
        href = str(link.get("href") or "")
        # An article is /noticias/{id}-{slug}; ".../noticias/1" is "Ver todas".
        if not re.search(r"/noticias/\d+-", href):
            continue
        text = " ".join(link.get_text(" ", strip=True).split())
        title = re.sub(r"^\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}\s*", "", text)
        if title:
            news.append(
                SourceNews(title=title[:300], url=href, published_at=_ff_news_date(text, now))
            )
    return news


def parse_ff_team(html: str, now: datetime) -> tuple[list[SourcePlayer], list[SourceNews]]:
    """Players (probable eleven first, then the rest, then the other absentees)
    and news of a team page."""
    try:
        soup = BeautifulSoup(html, "lxml")
        players = _ff_lineup(soup)
        if not players:
            logger.warning("lineup_intel: futbolfantasy team page without players")

        absences = _ff_absences(soup)
        merged: list[SourcePlayer] = []
        for player in players:
            if player.slug and player.slug in absences:
                status, report, _ = absences.pop(player.slug)
                player = SourcePlayer(
                    name=player.name,
                    probability=player.probability,
                    starter=player.starter,
                    status=_gravest({s for s in (status, player.status) if s}),
                    note=report,
                    slug=player.slug,
                )
            merged.append(player)
        for slug, (status, report, name) in absences.items():
            merged.append(
                SourcePlayer(
                    name=name,
                    probability=None,
                    starter=False,
                    status=status,
                    note=report,
                    slug=slug,
                )
            )
        return merged, _ff_news(soup, now)
    except Exception:
        logger.warning("lineup_intel: could not parse a futbolfantasy team page", exc_info=True)
        return [], []


# --- analiticafantasy --------------------------------------------------------------


def parse_af_matchday_links(html: str) -> list[str]:
    """Match paths (``/partido/{id}-{slug}``) of a matchday page, in order."""
    links = re.findall(r'href="(/partido/\d+-[a-z0-9-]+)"', html or "")
    return list(dict.fromkeys(links))


def _next_payload(html: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html, re.S)
    return "".join(json.loads(chunk) for chunk in chunks)


def _json_object_after(blob: str, key: str) -> dict[str, Any] | None:
    """The JSON object that follows ``key`` in ``blob``, by brace matching."""
    at = blob.find(key)
    if at < 0:
        return None
    start = blob.find("{", at)
    depth = 0
    index = start
    while index < len(blob):
        char = blob[index]
        if char == '"':
            index += 1
            while index < len(blob) and blob[index] != '"':
                index += 2 if blob[index] == "\\" else 1
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                parsed = json.loads(blob[start : index + 1])
                return parsed if isinstance(parsed, dict) else None
        index += 1
    return None


def _af_team_name(blob: str, side: str) -> str | None:
    match = re.search(rf'"{side}Team":\{{"id":\d+,"name":"((?:[^"\\]|\\.)*)"\}}', blob)
    return json.loads(f'"{match.group(1)}"') if match else None


def _af_player(raw: dict[str, Any]) -> SourcePlayer:
    extras = raw.get("playerExtras") or {}
    statuses: set[str] = set()
    if extras.get("isSanctioned"):
        statuses.add("sancionado")
    if extras.get("status") == "injured":
        statuses.add("lesionado")
    if extras.get("status") == "doubt":
        statuses.add("duda")
    note = " · ".join(
        str(part) for part in (extras.get("statusInfo"), extras.get("report")) if part
    )
    position_id = raw.get("positionId")
    return SourcePlayer(
        name=str(raw.get("name") or "").strip(),
        probability=_percent(raw.get("chance")),
        starter=bool(raw.get("esTitular")),
        status=_gravest(statuses),
        note=note or None,
        slug=raw.get("slug"),
        position=_AF_POSITIONS.get(position_id) if isinstance(position_id, int) else None,
    )


def parse_af_match(html: str) -> tuple[SourceTeam, SourceTeam] | None:
    """Home and away probable lineups of a match page, or None if unreadable."""
    try:
        blob = _next_payload(html)
        block = _json_object_after(blob, '"lineupBlock":')
        if not block:
            logger.warning("lineup_intel: analiticafantasy match page without lineupBlock")
            return None
        teams: list[SourceTeam] = []
        for side in ("home", "away"):
            data = block.get(side) or {}
            name = _af_team_name(blob, side)
            if not name:
                return None
            formation = str(data.get("formation") or "").replace("alineacion_", "") or None
            players = [_af_player(p) for p in data.get("players") or [] if p.get("name")]
            teams.append(SourceTeam(name=name, players=players, formation=formation))
        return teams[0], teams[1]
    except Exception:
        logger.warning(
            "lineup_intel: could not parse an analiticafantasy match page", exc_info=True
        )
        return None
