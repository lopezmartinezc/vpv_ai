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
    is_likely_penalty_taker,
    is_mover,
    is_peak_year,
    survival_haircut,
    tier_for,
)


class TestTierFor:
    """avg_pts → tier per position. Thresholds from DRAFT_SCORECARD.md."""

    def test_por_thresholds(self) -> None:
        # POR: elite ≥6.5, solid ≥6.0, normal ≥5.4
        assert tier_for("POR", 7.0) == "elite"
        assert tier_for("POR", 6.5) == "elite"
        assert tier_for("POR", 6.4) == "solid"
        assert tier_for("POR", 6.0) == "solid"
        assert tier_for("POR", 5.4) == "normal"
        assert tier_for("POR", 5.0) == "weak"

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
        )
        assert isinstance(e, ScorecardEnrichment)
        assert e.position_tier == "solid"
        assert e.survival_haircut_pct == 0.32
        assert e.effective_score == round(6.0 * (1 - 0.32), 2)
        assert e.is_mover is True
        assert e.is_peak_year is True
        assert e.is_likely_penalty_taker is True

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
        )
        assert e.position_tier == "elite"
        assert e.survival_haircut_pct == 0.22
        assert e.effective_score == round(7.5 * 0.78, 2)
        assert e.is_mover is False
        assert e.is_peak_year is False
        assert e.is_likely_penalty_taker is False

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
        )
        assert e.is_peak_year is False
        assert e.is_mover is False  # last_team None ⇒ inconclusive
