"""Scorecard heuristics applied on top of the Ensemble draft-value model.

The Ensemble model (`service_draft.py`) tops out at Spearman 0.718. The
extra signal beyond that comes from heuristic overrides described in
``docs/DRAFT_SCORECARD.md``: per-position tiers, survival haircuts,
and warning flags (movers, year-peakers, likely penalty-takers).

This module exposes pure functions so the live-draft endpoint can
enrich each ``DraftValuePlayer`` independently and so the math is
easy to unit-test against the documented thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tiers — avg_pts thresholds per position, from DRAFT_SCORECARD.md.
# An entry maps the tier name to the *minimum* avg_pts that qualifies.
# Anything below the lowest tier minimum falls into "weak".
# ---------------------------------------------------------------------------

_TIER_THRESHOLDS: dict[str, dict[str, float]] = {
    "POR": {"elite": 6.5, "solid": 6.0, "normal": 5.4},
    "DEF": {"elite": 6.6, "solid": 5.8, "normal": 4.9},
    "MED": {"elite": 6.1, "solid": 5.3, "normal": 4.4},
    "DEL": {"elite": 7.2, "solid": 5.4, "normal": 4.2},
}

# Survival haircut applied to the ensemble score before ranking.
# Same brackets used across positions — they refer to avg_pts of the
# previous season (the most-recent reliable signal we have).
_HAIRCUT_BRACKETS: list[tuple[float, float]] = [
    (7.0, 0.22),  # avg_pts > 7 -> 22% off (elite, lowest fragility)
    (6.0, 0.27),  # 6.0-7.0 -> 27%
    (5.0, 0.32),  # 5.0-6.0 (typical round 4-8 picks) -> 32%
    (0.0, 0.48),  # < 5.0 -> 48%
]


@dataclass
class ScorecardEnrichment:
    position_tier: str
    survival_haircut_pct: float
    effective_score: float
    is_mover: bool
    is_peak_year: bool
    is_likely_penalty_taker: bool


def tier_for(position: str, avg_pts: float) -> str:
    """Return ``"elite" | "solid" | "normal" | "weak"`` per position.

    Falls back to "weak" if the position is unrecognised (defensive —
    should never happen for La Liga but the source data can include
    unusual codes after roster syncs)."""
    thresholds = _TIER_THRESHOLDS.get(position)
    if thresholds is None:
        return "weak"
    if avg_pts >= thresholds["elite"]:
        return "elite"
    if avg_pts >= thresholds["solid"]:
        return "solid"
    if avg_pts >= thresholds["normal"]:
        return "normal"
    return "weak"


def survival_haircut(avg_pts: float) -> float:
    """Return the % to trim from the ensemble score for survival risk.

    Higher avg_pts → lower haircut (these players have established
    themselves and are less likely to fall off the cliff next season).
    R4-8 picks get the heaviest non-tail haircut at 32%."""
    for threshold, haircut in _HAIRCUT_BRACKETS:
        if avg_pts >= threshold:
            return haircut
    return _HAIRCUT_BRACKETS[-1][1]


def is_peak_year(
    last_avg_pts: float,
    career_avg_pts: float | None,
    min_lift: float = 0.5,
) -> bool:
    """True when the latest season is notably better than the career
    baseline — the scorecard flags this as regression risk.

    Default lift = 0.5 pts/match. Anything bigger than that suggests
    a year-pick that the operator should discount mentally (~0.7 pts
    per the document).
    """
    if career_avg_pts is None:
        return False
    return last_avg_pts - career_avg_pts >= min_lift


def is_mover(current_team: str | None, last_team: str | None) -> bool:
    """True when the player changed clubs since the previous season."""
    if not current_team or not last_team:
        return False
    return current_team.strip() != last_team.strip()


def is_likely_penalty_taker(
    position: str,
    penalty_goals: int,
    penalties_missed: int,
) -> bool:
    """Heuristic: ≥2 penalty attempts last season → still the taker.

    Per the scorecard: persists only 44% YoY, but if no info to the
    contrary is available, attempt count is the best signal we have
    from the DB."""
    if position != "DEL":
        return False
    return (penalty_goals + penalties_missed) >= 2


def enrich(
    *,
    position: str,
    ensemble_score: float,
    avg_pts: float,
    career_avg_pts: float | None,
    current_team: str | None,
    last_team: str | None,
    penalty_goals: int,
    penalties_missed: int,
) -> ScorecardEnrichment:
    """Compute all scorecard fields for a single player in one pass.

    Mirrors the structure of the runtime data we have for the Liga
    pre-season draft: previous-season avg_pts, career baseline, both
    team names, penalty counts. Anything missing degrades gracefully
    to ``False``/no haircut adjustment.
    """
    haircut = survival_haircut(avg_pts)
    effective = ensemble_score * (1 - haircut)
    return ScorecardEnrichment(
        position_tier=tier_for(position, avg_pts),
        survival_haircut_pct=round(haircut, 2),
        effective_score=round(effective, 2),
        is_mover=is_mover(current_team, last_team),
        is_peak_year=is_peak_year(avg_pts, career_avg_pts),
        is_likely_penalty_taker=is_likely_penalty_taker(position, penalty_goals, penalties_missed),
    )
