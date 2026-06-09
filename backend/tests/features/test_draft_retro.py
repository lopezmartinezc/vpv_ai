"""Unit tests for the pure helpers in service_draft_retro.

The DB-touching methods are integration-tested elsewhere; here we
pin the math down so refactors can't silently change steal/bust
boundaries or break the Spearman calculation.
"""

from __future__ import annotations

import pytest

from src.features.stats.schemas_draft_retro import BacktestPoint
from src.features.stats.service_draft_retro import (
    aggregate_buckets,
    compute_slot_curve,
    compute_spearman,
    tag_pick,
)


class TestComputeSlotCurve:
    def test_simple_medians(self) -> None:
        picks = [
            (1, 200.0),
            (1, 250.0),
            (1, 100.0),  # median of slot 1 = 200
            (2, 150.0),
            (2, 50.0),  # median of slot 2 = 100
        ]
        curve = compute_slot_curve(picks)
        assert curve[1] == 200.0
        assert curve[2] == 100.0

    def test_empty(self) -> None:
        assert compute_slot_curve([]) == {}

    def test_singleton_slot(self) -> None:
        # A slot with one pick is its own median.
        curve = compute_slot_curve([(7, 42.0)])
        assert curve[7] == 42.0

    def test_resists_extreme_outliers(self) -> None:
        # 999 outlier shouldn't drag the median.
        picks = [(1, 50.0), (1, 60.0), (1, 70.0), (1, 999.0)]
        curve = compute_slot_curve(picks)
        # median([50, 60, 70, 999]) = 65
        assert curve[1] == 65.0


class TestTagPick:
    def test_top_quartile_is_steal(self) -> None:
        deltas = [-50, -10, -5, 0, 5, 10, 50]  # 7 values
        # Q1 ≈ -10, Q3 ≈ 10 (inclusive method)
        assert tag_pick(50, deltas) == "steal"
        assert tag_pick(10, deltas) == "steal"

    def test_bottom_quartile_is_bust(self) -> None:
        deltas = [-50, -10, -5, 0, 5, 10, 50]
        assert tag_pick(-50, deltas) == "bust"
        assert tag_pick(-10, deltas) == "bust"

    def test_middle_is_normal(self) -> None:
        deltas = [-50, -10, -5, 0, 5, 10, 50]
        assert tag_pick(0, deltas) == "normal"
        assert tag_pick(-5, deltas) == "normal"

    def test_tiny_sample_uses_median_split(self) -> None:
        # < 4 picks falls back to median split.
        deltas = [10.0, 20.0, 30.0]  # median 20
        assert tag_pick(30.0, deltas) == "steal"
        assert tag_pick(10.0, deltas) == "bust"
        assert tag_pick(20.0, deltas) == "normal"

    def test_empty_returns_normal(self) -> None:
        assert tag_pick(100.0, []) == "normal"


class TestSpearman:
    def test_perfect_positive_rank(self) -> None:
        # Both ranked the same way.
        assert compute_spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == pytest.approx(1.0)

    def test_perfect_negative_rank(self) -> None:
        assert compute_spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10]) == pytest.approx(-1.0)

    def test_unrelated_returns_low(self) -> None:
        rho = compute_spearman([1, 2, 3, 4], [3, 1, 4, 2])
        assert -1.0 <= rho <= 1.0

    def test_too_short_returns_zero(self) -> None:
        assert compute_spearman([1, 2], [3, 4]) == 0.0
        assert compute_spearman([], []) == 0.0

    def test_length_mismatch_returns_zero(self) -> None:
        assert compute_spearman([1, 2, 3], [4, 5]) == 0.0

    def test_constant_series_returns_zero_not_nan(self) -> None:
        # spearmanr returns nan when one series is constant — we guard.
        assert compute_spearman([5, 5, 5, 5], [1, 2, 3, 4]) == 0.0


class TestAggregateBuckets:
    def _make_point(self, *, signal: str, tier: str, actual: float) -> BacktestPoint:
        return BacktestPoint(
            player_id=1,
            player_name="x",
            position="MED",
            seasons_history=1,
            predicted_effective_score=5.0,
            predicted_signal=signal,
            predicted_tier=tier,
            actual_total_points=actual,
            actual_avg_points=actual / 30,
            actual_matchdays_played=30,
        )

    def test_groups_by_signal(self) -> None:
        points = [
            self._make_point(signal="strong_buy", tier="elite", actual=200),
            self._make_point(signal="strong_buy", tier="elite", actual=180),
            self._make_point(signal="avoid", tier="weak", actual=50),
        ]
        buckets = aggregate_buckets(points, "predicted_signal")
        assert buckets["strong_buy"].n == 2
        assert buckets["strong_buy"].mean_actual == 190.0
        assert buckets["strong_buy"].median_actual == 190.0
        assert buckets["avoid"].n == 1
        assert buckets["avoid"].mean_actual == 50.0

    def test_groups_by_tier(self) -> None:
        points = [
            self._make_point(signal="buy", tier="elite", actual=150),
            self._make_point(signal="hold", tier="elite", actual=200),
            self._make_point(signal="hold", tier="normal", actual=80),
        ]
        buckets = aggregate_buckets(points, "predicted_tier")
        assert buckets["elite"].n == 2
        assert buckets["elite"].median_actual == 175.0
        assert buckets["normal"].n == 1

    def test_empty_points(self) -> None:
        assert aggregate_buckets([], "predicted_signal") == {}


class TestSanityChecksOnAcceptanceCriteria:
    """High-level sanity checks tying the helpers to the plan."""

    def test_steal_means_above_baseline(self) -> None:
        # If a pick scored 250 and the slot median is 100, delta=150 → steal.
        curve = compute_slot_curve([(1, 100.0), (1, 90.0), (1, 110.0)])
        delta = 250 - curve[1]
        # In a single-draft context with 4+ picks, the top one is "steal".
        all_deltas = [delta, -20.0, 5.0, -10.0]
        assert tag_pick(delta, all_deltas) == "steal"

    def test_bust_means_below_baseline(self) -> None:
        # If a pick scored 20 and the slot median is 150, delta=-130 → bust.
        curve = compute_slot_curve([(1, 150.0), (1, 140.0), (1, 160.0)])
        delta = 20 - curve[1]
        all_deltas = [delta, 50.0, 10.0, 30.0]
        assert tag_pick(delta, all_deltas) == "bust"
