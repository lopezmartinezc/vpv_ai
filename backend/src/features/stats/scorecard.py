"""Scorecard heuristics applied on top of the Ensemble draft-value model.

The Ensemble model (`service_draft.py`) tops out at Spearman 0.718. The
extra signal beyond that comes from heuristic overrides described in
``docs/DRAFT_SCORECARD.md``: per-position tiers, survival haircuts,
and warning flags (movers, year-peakers, likely penalty-takers, bench
risk).

This module exposes pure functions so the live-draft endpoint can
enrich each ``DraftValuePlayer`` independently and so the math is
easy to unit-test against the documented thresholds.

Refinement 2026-06-09 (Claude Fable analysis):
- POR no longer uses tiered avg_pts — the range (p25=5.4, p90=7.6) is
  too narrow for tiers to mean anything; value comes from the team.
  Returns "team_dependent".
- `is_bench_risk` flag added: starter_pct < 0.79 or games_played < 22
  (p50 thresholds from the analysis). Universal Step 0 of the
  decision-tree: availability beats everything else.
- Mover penalty *hints* (POR ±2, DEL/MED ±1, DEF ±1) exposed for the
  UI to display; the actual application requires last-team standings
  data we don't have, so this is informational, not applied to the
  effective_score.
- Penalty taker docstring notes 44% YoY persistence — UI should warn
  the admin to verify for the current season.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tiers — avg_pts thresholds per position, from DRAFT_SCORECARD.md.
# An entry maps the tier name to the *minimum* avg_pts that qualifies.
# Anything below the lowest tier minimum falls into "weak".
#
# POR is intentionally NOT tiered: the goalkeeper avg_pts range is so
# narrow that tiers are noise. The value comes from the team they play
# for (clean sheets etc), which we can't read from the player history.
# ---------------------------------------------------------------------------

_TIER_THRESHOLDS: dict[str, dict[str, float]] = {
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

# Bench-risk thresholds (median, p50, of the seasons-6-to-8 dataset).
# A player below either limit is at meaningful risk of not playing
# enough to matter — Step 0 of the decision-tree.
_BENCH_RISK_STARTER_PCT = 0.79
_BENCH_RISK_MIN_GAMES = 22

# How many points to mentally subtract per mover when the team-quality
# delta is *large* (top-4 -> recently-promoted, or vice versa). Used
# only as a UI hint; the production effective_score doesn't subtract
# anything because we don't have prior-team standings to gauge the
# delta. The admin applies the hint manually.
_MOVER_PENALTY_HINTS: dict[str, float] = {
    "POR": 2.0,
    "DEL": 1.0,
    "MED": 1.0,
    "DEF": 1.0,
}


@dataclass
class ScorecardEnrichment:
    position_tier: str
    survival_haircut_pct: float
    effective_score: float
    is_mover: bool
    is_peak_year: bool
    is_likely_penalty_taker: bool
    is_bench_risk: bool
    # Informational hint, in pts — applied manually by the admin when
    # the player switches to a much weaker/stronger team. None for
    # non-movers; positive value for movers.
    mover_penalty_hint: float | None


def tier_for(position: str, avg_pts: float) -> str:
    """Return ``"elite" | "solid" | "normal" | "weak"`` per position.

    POR is a special case: returns ``"team_dependent"`` because the
    goalkeeper avg_pts range is too narrow for tiers to discriminate.
    Falls back to "weak" for unknown positions.
    """
    if position == "POR":
        return "team_dependent"
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

    Per the scorecard the role only persists 44% YoY — UI should
    warn the admin to verify the current-season taker before
    acting on this flag.
    """
    if position != "DEL":
        return False
    return (penalty_goals + penalties_missed) >= 2


def is_bench_risk(
    starter_pct: float,
    games_played: int,
) -> bool:
    """Step 0 of the decision-tree: is this player at availability risk?

    Two-condition OR: rotating out of XI (starter_pct < 0.79) OR
    playing too few matches in the season to accumulate points
    (games_played < 22). p50 thresholds from seasons 6-8.
    """
    return starter_pct < _BENCH_RISK_STARTER_PCT or games_played < _BENCH_RISK_MIN_GAMES


def mover_penalty_hint_for(position: str) -> float:
    """How many pts to mentally subtract if the team-quality jump is large.

    Returns the magnitude (always positive). The admin applies the
    sign manually based on whether the new team is much weaker (-)
    or much stronger (+).
    """
    return _MOVER_PENALTY_HINTS.get(position, 1.0)


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
    starter_pct: float,
    games_played: int,
) -> ScorecardEnrichment:
    """Compute all scorecard fields for a single player in one pass.

    Mirrors the structure of the runtime data we have for the Liga
    pre-season draft: previous-season avg_pts, career baseline, both
    team names, penalty counts, starter rate, games. Anything missing
    degrades gracefully to ``False``/no haircut adjustment.
    """
    haircut = survival_haircut(avg_pts)
    effective = ensemble_score * (1 - haircut)
    mover = is_mover(current_team, last_team)
    return ScorecardEnrichment(
        position_tier=tier_for(position, avg_pts),
        survival_haircut_pct=round(haircut, 2),
        effective_score=round(effective, 2),
        is_mover=mover,
        is_peak_year=is_peak_year(avg_pts, career_avg_pts),
        is_likely_penalty_taker=is_likely_penalty_taker(position, penalty_goals, penalties_missed),
        is_bench_risk=is_bench_risk(starter_pct, games_played),
        mover_penalty_hint=mover_penalty_hint_for(position) if mover else None,
    )
