"""The eleven worth the most this matchday, and why.

A player is worth what he scores if he plays times the chance that he plays:

* what he scores if he plays is the forecast's ``xpts_if_plays`` — the
  prediction BEFORE its own starter discount, so the chance is not counted
  twice;
* the chance comes from the probable lineups when there are any (the mean of
  the sources that give a percentage): they know this week's news, recent
  history does not. Without them, the share of recent matches started;
* injured, suspended or unavailable is zero whatever the percentage says; a
  doubt with no percentage from any source halves the historical share. When a
  source gives a percentage, the doubt is already in it.

Then every valid formation is filled with the best of each position, and the
highest total wins; on a tie, the higher ceiling.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

POSITIONS = ("POR", "DEF", "MED", "DEL")
OUT_STATUSES = ("sancionado", "no_disponible", "lesionado")
SOURCE_LABELS = {"futbolfantasy": "FF", "analiticafantasy": "AF"}


@dataclass(frozen=True)
class Candidate:
    player_id: int
    name: str
    position: str
    team_name: str
    # None: no forecast, usually because his team does not play this matchday.
    xpts_if_plays: float | None
    # The forecast's spread (ceiling minus expected), for the tie-break.
    spread: float = 0.0
    # Share of recent matches started, 0-100.
    starter_pct: float | None = None
    # Source → probability 0-100 (None when a source lists him without one).
    source_probs: Mapping[str, int | None] = field(default_factory=dict)
    statuses: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Valued:
    candidate: Candidate
    play_prob: float
    value: float
    ceiling: float
    basis: str


@dataclass(frozen=True)
class Formation:
    name: str
    defenders: int
    midfielders: int
    forwards: int

    def slots(self) -> dict[str, int]:
        return {"POR": 1, "DEF": self.defenders, "MED": self.midfielders, "DEL": self.forwards}


@dataclass(frozen=True)
class Suggestion:
    formation: str
    eleven: list[Valued]
    bench: list[Valued]
    total: float


def _pct(value: float) -> str:
    return f"{round(value)} %"


def play_probability(c: Candidate) -> tuple[float, str]:
    """The chance he plays, and where it comes from."""
    out = next((s for s in OUT_STATUSES if s in c.statuses), None)
    if out is not None:
        return 0.0, out.replace("_", " ")
    given = {s: p for s, p in c.source_probs.items() if p is not None}
    if given:
        prob = sum(given.values()) / len(given) / 100
        detail = " · ".join(f"{SOURCE_LABELS.get(s, s)} {p} %" for s, p in sorted(given.items()))
        return prob, f"alineaciones probables ({detail})"
    if c.starter_pct is not None:
        prob = c.starter_pct / 100
        if "duda" in c.statuses:
            return (
                prob / 2,
                f"duda; titular en el {_pct(c.starter_pct)} de sus ultimos partidos, a la mitad",
            )
        return prob, f"titular en el {_pct(c.starter_pct)} de sus ultimos partidos"
    return 0.0, "sin datos de titularidad"


def value_of(c: Candidate) -> Valued:
    if c.xpts_if_plays is None:
        return Valued(c, 0.0, 0.0, 0.0, "sin partido ni prevision esta jornada")
    prob, basis = play_probability(c)
    return Valued(
        candidate=c,
        play_prob=round(prob, 2),
        value=round(c.xpts_if_plays * prob, 2),
        ceiling=round((c.xpts_if_plays + c.spread) * prob, 2),
        basis=basis,
    )


def _rank(items: list[Valued]) -> list[Valued]:
    return sorted(items, key=lambda v: (-v.value, -v.ceiling, v.candidate.name))


def best_lineup(
    candidates: Sequence[Candidate],
    formations: Sequence[Formation],
    only: str | None = None,
) -> Suggestion | None:
    """The best valid eleven, or None if the squad cannot fill any formation.

    ``only`` restricts the search to one formation (e.g. "1-4-4-2").
    """
    valued = [value_of(c) for c in candidates]
    by_position = {
        pos: _rank([v for v in valued if v.candidate.position == pos]) for pos in POSITIONS
    }

    best: tuple[float, float, str] | None = None
    chosen: tuple[Formation, list[Valued]] | None = None
    for formation in formations:
        if only and formation.name != only:
            continue
        slots = formation.slots()
        if any(len(by_position[pos]) < n for pos, n in slots.items()):
            continue
        eleven = [v for pos in POSITIONS for v in by_position[pos][: slots[pos]]]
        total = round(sum(v.value for v in eleven), 2)
        ceiling = round(sum(v.ceiling for v in eleven), 2)
        # Higher total, then higher ceiling; the name only makes the choice stable.
        key = (total, ceiling, formation.name)
        if best is None or (key[0], key[1]) > (best[0], best[1]):
            best, chosen = key, (formation, eleven)
    if chosen is None or best is None:
        return None

    formation, eleven = chosen
    picked = {v.candidate.player_id for v in eleven}
    bench = _rank([v for v in valued if v.candidate.player_id not in picked])
    return Suggestion(formation=formation.name, eleven=eleven, bench=bench, total=best[0])
