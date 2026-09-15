"""Match a source's team and player names to ours.

futbolfantasy needs none of this: its slugs are ours. analiticafantasy writes
"Celta Vigo" for our "Celta" and "Dmitrovic" for our "Marko Dmitrović", so its
names are matched as sets of words, accents and case aside — the approach the
Marca ratings already use — and only a clear, unique best counts. Anything
doubtful stays unmatched: shown by its name, never pinned on the wrong player.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from src.features.lineup_intel.parsers import SourcePlayer

# Words that tell no team apart.
_TEAM_NOISE = {"real", "club", "cf", "fc", "cd", "ud", "sd", "rcd", "de", "la", "el", "sad"}


def normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFD", text or "")
    stripped = "".join(c for c in stripped if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stripped).split())


def words(text: str) -> set[str]:
    """Words of two letters or more; digits (the ids in some slugs) are dropped."""
    return {w for w in normalize(text).split() if len(w) >= 2 and not w.isdigit()}


@dataclass(frozen=True)
class TeamRef:
    id: int
    name: str
    slug: str
    short_name: str | None = None


@dataclass(frozen=True)
class RosterPlayer:
    id: int
    team_id: int
    display_name: str
    slug: str
    position: str
    aliases: str | None = None


def match_team(name: str, teams: Sequence[TeamRef]) -> int | None:
    """Our team for a source's team name: the clear best by shared words.

    Sharing the first meaningful word counts extra, so "Atletico Madrid" goes
    to "Atlético" and not to "Real Madrid".
    """
    source = [w for w in normalize(name).split() if w not in _TEAM_NOISE]
    if not source:
        return None
    scored: list[tuple[float, int]] = []
    for team in teams:
        # The source's words are already free of noise, so ours need not be.
        ours = words(f"{team.name} {team.slug.replace('-', ' ')} {team.short_name or ''}")
        shared = set(source) & ours
        if not shared:
            continue
        scored.append((len(shared) + (0.5 if source[0] in ours else 0.0), team.id))
    scored.sort(reverse=True)
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return None
    return scored[0][1]


def match_player(player: SourcePlayer, roster: Sequence[RosterPlayer]) -> int | None:
    """Our player for a source's player, within one team: the clear best.

    Compares the words of the source's name and slug with those of our name,
    slug and aliases. A shared long word counts; the same position breaks ties.
    """
    slug = re.sub(r"-\d+$", "", player.slug or "")
    source = {w for w in words(f"{player.name} {slug}") if len(w) >= 3}
    if not source:
        return None
    scored: list[tuple[float, int]] = []
    for candidate in roster:
        ours = words(f"{candidate.display_name} {candidate.slug} {candidate.aliases or ''}")
        shared = source & ours
        if not shared:
            continue
        score = float(len(shared))
        if player.position and player.position == candidate.position:
            score += 0.5
        scored.append((score, candidate.id))
    scored.sort(reverse=True)
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return None
    return scored[0][1]
