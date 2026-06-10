"""Unit tests for the scorecard module.

Verifies the per-position thresholds and the survival-haircut brackets
match docs/DRAFT_SCORECARD.md exactly. These tests are the contract:
if a threshold changes in the doc, this file should fail until the
code is updated.
"""

from __future__ import annotations

from src.features.stats.scorecard import (
    ScorecardEnrichment,
    enrich,
    is_bench_risk,
    is_likely_penalty_taker,
    is_mover,
    is_peak_year,
    mover_penalty_hint_for,
    survival_haircut,
    tier_for,
)


class TestTierFor:
    """avg_pts → tier per position. Thresholds from DRAFT_SCORECARD.md."""

    def test_por_returns_team_dependent_regardless_of_avg(self) -> None:
        # POR avg_pts range is too narrow for tiers to mean anything
        # (p25=5.4 to p90=7.6). The scorecard says "value the team",
        # so the tier is always "team_dependent".
        assert tier_for("POR", 7.0) == "team_dependent"
        assert tier_for("POR", 6.0) == "team_dependent"
        assert tier_for("POR", 4.0) == "team_dependent"

    def test_def_thresholds(self) -> None:
        # DEF: elite ≥6.6, solid ≥5.8, normal ≥4.9
        assert tier_for("DEF", 7.0) == "elite"
        assert tier_for("DEF", 6.6) == "elite"
        assert tier_for("DEF", 6.5) == "solid"
        assert tier_for("DEF", 5.8) == "solid"
        assert tier_for("DEF", 4.9) == "normal"
        assert tier_for("DEF", 4.0) == "weak"

    def test_med_thresholds(self) -> None:
        # MED: elite ≥6.1, solid ≥5.3, normal ≥4.4
        assert tier_for("MED", 7.0) == "elite"
        assert tier_for("MED", 6.1) == "elite"
        assert tier_for("MED", 5.3) == "solid"
        assert tier_for("MED", 4.4) == "normal"
        assert tier_for("MED", 3.0) == "weak"

    def test_del_thresholds(self) -> None:
        # DEL: elite ≥7.2, solid ≥5.4, normal ≥4.2 — the widest range.
        assert tier_for("DEL", 8.0) == "elite"
        assert tier_for("DEL", 7.2) == "elite"
        assert tier_for("DEL", 7.0) == "solid"
        assert tier_for("DEL", 5.4) == "solid"
        assert tier_for("DEL", 4.2) == "normal"
        assert tier_for("DEL", 4.1) == "weak"

    def test_unknown_position_falls_back_to_weak(self) -> None:
        assert tier_for("???", 10.0) == "weak"


class TestSurvivalHaircut:
    """Brackets from DRAFT_SCORECARD.md: 22% / 27% / 32% / 48%."""

    def test_elite(self) -> None:
        assert survival_haircut(8.0) == 0.22
        assert survival_haircut(7.0) == 0.22

    def test_above_average(self) -> None:
        assert survival_haircut(6.9) == 0.27
        assert survival_haircut(6.0) == 0.27

    def test_round_4_8_range(self) -> None:
        # The 5.0-6.0 band is the costly one for draft round 4-8.
        assert survival_haircut(5.5) == 0.32
        assert survival_haircut(5.0) == 0.32

    def test_low_tier(self) -> None:
        assert survival_haircut(4.9) == 0.48
        assert survival_haircut(0.0) == 0.48


class TestIsPeakYear:
    def test_last_well_above_career(self) -> None:
        assert is_peak_year(last_avg_pts=7.0, career_avg_pts=6.0) is True

    def test_last_at_career(self) -> None:
        assert is_peak_year(last_avg_pts=6.0, career_avg_pts=6.0) is False

    def test_last_below_career(self) -> None:
        assert is_peak_year(last_avg_pts=5.0, career_avg_pts=6.0) is False

    def test_marginal_lift_below_default_threshold(self) -> None:
        # default min_lift = 0.5
        assert is_peak_year(last_avg_pts=6.4, career_avg_pts=6.0) is False

    def test_no_career_means_no_peak_flag(self) -> None:
        assert is_peak_year(last_avg_pts=10.0, career_avg_pts=None) is False


class TestIsMover:
    def test_same_team(self) -> None:
        assert is_mover("Real Madrid", "Real Madrid") is False

    def test_different_team(self) -> None:
        assert is_mover("Real Madrid", "Sevilla") is True

    def test_either_missing_returns_false(self) -> None:
        assert is_mover(None, "Real Madrid") is False
        assert is_mover("Real Madrid", None) is False
        assert is_mover(None, None) is False

    def test_whitespace_is_normalised(self) -> None:
        assert is_mover(" Real Madrid ", "Real Madrid") is False


class TestPenaltyTaker:
    def test_del_with_two_attempts_qualifies(self) -> None:
        assert is_likely_penalty_taker("DEL", penalty_goals=2, penalties_missed=0) is True
        assert is_likely_penalty_taker("DEL", penalty_goals=0, penalties_missed=2) is True

    def test_del_with_single_attempt_does_not_qualify(self) -> None:
        assert is_likely_penalty_taker("DEL", penalty_goals=1, penalties_missed=0) is False

    def test_non_del_never_qualifies(self) -> None:
        # The scorecard only credits penalty-taker status to forwards.
        assert is_likely_penalty_taker("MED", penalty_goals=5, penalties_missed=2) is False
        assert is_likely_penalty_taker("POR", penalty_goals=5, penalties_missed=0) is False


class TestBenchRisk:
    """Step 0 of the decision-tree — availability is the universal filter."""

    def test_low_starter_pct_is_bench_risk(self) -> None:
        # starter_pct < 0.79 trips the flag even with full games count
        assert is_bench_risk(starter_pct=0.50, games_played=30) is True

    def test_few_games_is_bench_risk(self) -> None:
        # games < 22 trips the flag even with a perfect starter rate
        assert is_bench_risk(starter_pct=1.0, games_played=15) is True

    def test_solid_starter_no_risk(self) -> None:
        # p75 of the dataset — clearly safe.
        assert is_bench_risk(starter_pct=0.93, games_played=27) is False

    def test_threshold_boundaries(self) -> None:
        # Exactly at p50 should still trip — the threshold is strict <.
        assert is_bench_risk(starter_pct=0.79, games_played=22) is False
        assert is_bench_risk(starter_pct=0.78, games_played=22) is True
        assert is_bench_risk(starter_pct=0.79, games_played=21) is True


class TestMoverPenaltyHint:
    """Magnitudes mirror docs/DRAFT_SCORECARD.md mover-sensitivity table."""

    def test_por_is_double(self) -> None:
        # GK environment is the biggest swing — the team brings the
        # clean-sheet points.
        assert mover_penalty_hint_for("POR") == 2.0

    def test_outfield_positions_are_one(self) -> None:
        assert mover_penalty_hint_for("DEF") == 1.0
        assert mover_penalty_hint_for("MED") == 1.0
        assert mover_penalty_hint_for("DEL") == 1.0

    def test_unknown_position_defaults_to_one(self) -> None:
        assert mover_penalty_hint_for("???") == 1.0


class TestEnrich:
    """End-to-end check that the dataclass fields line up."""

    def test_round_4_8_mover_with_peak_year(self) -> None:
        # Classic 'mover after a peak' — the scorecard says discount
        # heavily. Avg 5.5 ⇒ tier=solid for DEL, haircut=0.32.
        e = enrich(
            position="DEL",
            ensemble_score=6.0,
            avg_pts=5.5,
            career_avg_pts=4.5,
            current_team="Sevilla",
            last_team="Valencia",
            penalty_goals=4,
            penalties_missed=1,
            starter_pct=0.85,
            games_played=28,
        )
        assert isinstance(e, ScorecardEnrichment)
        assert e.position_tier == "solid"
        assert e.survival_haircut_pct == 0.32
        assert e.effective_score == round(6.0 * (1 - 0.32), 2)
        assert e.is_mover is True
        assert e.is_peak_year is True
        assert e.is_likely_penalty_taker is True
        assert e.is_bench_risk is False
        assert e.mover_penalty_hint == 1.0  # DEL

    def test_elite_stayer_no_flags(self) -> None:
        e = enrich(
            position="MED",
            ensemble_score=7.5,
            avg_pts=7.0,
            career_avg_pts=6.9,
            current_team="Barcelona",
            last_team="Barcelona",
            penalty_goals=0,
            penalties_missed=0,
            starter_pct=0.95,
            games_played=32,
        )
        assert e.position_tier == "elite"
        assert e.survival_haircut_pct == 0.22
        assert e.effective_score == round(7.5 * 0.78, 2)
        assert e.is_mover is False
        assert e.is_peak_year is False
        assert e.is_likely_penalty_taker is False
        assert e.is_bench_risk is False
        assert e.mover_penalty_hint is None  # non-movers get no hint

    def test_missing_career_baseline_does_not_flag_peak(self) -> None:
        e = enrich(
            position="MED",
            ensemble_score=6.0,
            avg_pts=6.5,
            career_avg_pts=None,
            current_team="Barcelona",
            last_team=None,
            penalty_goals=0,
            penalties_missed=0,
            starter_pct=0.85,
            games_played=25,
        )
        assert e.is_peak_year is False
        assert e.is_mover is False  # last_team None ⇒ inconclusive

    def test_por_mover_carries_double_hint(self) -> None:
        # GK changing club: scorecard wants ~±2 pts hint shown.
        e = enrich(
            position="POR",
            ensemble_score=6.5,
            avg_pts=6.5,
            career_avg_pts=6.3,
            current_team="Real Oviedo",  # newly promoted
            last_team="Real Madrid",
            penalty_goals=0,
            penalties_missed=0,
            starter_pct=0.95,
            games_played=30,
        )
        assert e.position_tier == "team_dependent"  # POR has no avg-based tier
        assert e.is_mover is True
        assert e.mover_penalty_hint == 2.0

    def test_bench_risk_propagates(self) -> None:
        e = enrich(
            position="DEF",
            ensemble_score=5.0,
            avg_pts=5.0,
            career_avg_pts=5.0,
            current_team="Sevilla",
            last_team="Sevilla",
            penalty_goals=0,
            penalties_missed=0,
            starter_pct=0.40,
            games_played=15,
        )
        assert e.is_bench_risk is True
