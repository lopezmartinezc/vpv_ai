"""A final played over three jornadas, best of three.

Rules agreed for the Liga 2026-27 playoffs (Apertura and Clausura):

* whoever wins two jornadas wins the final; if one side wins the first two,
  the third is not played;
* a drawn jornada goes to whoever has the better point difference over the
  OTHER two jornadas of the final. Its own difference is nought, so that is
  the difference over the whole final, and it can only be settled once both
  other jornadas are scored: a draw always takes the final to its third;
* if that difference is level too, the better regular-phase seed takes it,
  the same rule as a drawn cuartos or semis.

Pure: no DB. The engine hands in the three legs in order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Side = Literal["a", "b"]
LegResult = Literal["a", "b", "pending", "not_needed"]
DecidedBy = Literal["points", "difference", "seed"]


@dataclass(frozen=True)
class Leg:
    matchup_id: int
    matchday_number: int | None
    score_a: int | None
    score_b: int | None

    @property
    def scored(self) -> bool:
        return self.score_a is not None and self.score_b is not None


@dataclass(frozen=True)
class LegOutcome:
    leg: Leg
    result: LegResult
    decided_by: DecidedBy | None = None


@dataclass(frozen=True)
class SeriesResult:
    wins_a: int
    wins_b: int
    winner: Side | None
    legs: list[LegOutcome]


def resolve_best_of_three(legs: Sequence[Leg], better_seed: Side) -> SeriesResult:
    """Who has won each leg so far, and the final if it is settled."""
    if len(legs) != 3:
        raise ValueError(f"a best-of-three final has 3 legs, got {len(legs)}")

    results: list[LegResult | Literal["draw"]] = []
    decided_by: list[DecidedBy | None] = []
    straight = {"a": 0, "b": 0}
    for leg in legs:
        if straight["a"] == 2 or straight["b"] == 2:
            results.append("not_needed")
            decided_by.append(None)
        elif not leg.scored:
            results.append("pending")
            decided_by.append(None)
        elif leg.score_a != leg.score_b:
            side: Side = "a" if leg.score_a > leg.score_b else "b"  # type: ignore[operator]
            straight[side] += 1
            results.append(side)
            decided_by.append("points")
        else:
            results.append("draw")
            decided_by.append(None)

    # A drawn leg looks at the other two, so it waits until both are scored.
    for i, result in enumerate(results):
        if result != "draw":
            continue
        others = [leg for j, leg in enumerate(legs) if j != i]
        if not all(leg.scored for leg in others):
            results[i] = "pending"
            continue
        difference = sum((leg.score_a or 0) - (leg.score_b or 0) for leg in others)
        if difference:
            results[i] = "a" if difference > 0 else "b"
            decided_by[i] = "difference"
        else:
            results[i] = better_seed
            decided_by[i] = "seed"

    wins_a = results.count("a")
    wins_b = results.count("b")
    winner: Side | None = "a" if wins_a >= 2 else "b" if wins_b >= 2 else None
    return SeriesResult(
        wins_a=wins_a,
        wins_b=wins_b,
        winner=winner,
        legs=[
            LegOutcome(leg=leg, result=result, decided_by=how)  # type: ignore[arg-type]
            for leg, result, how in zip(legs, results, decided_by, strict=True)
        ],
    )
