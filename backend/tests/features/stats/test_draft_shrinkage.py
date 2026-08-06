"""Early-season shrinkage blend for the Liga draft value model.

The Liga draft happens after 4-8 matchdays, so the model must blend the
noisy current-season average with the historical prior. An offline backtest
over 6 complete seasons (real data) showed empirical-Bayes shrinkage with
k=4 lifts Spearman vs rest-of-season points from ~0.76 (history-only) to
~0.83 — beating both the history-only and current-only extremes.

Weight on the current signal = n_current / (n_current + k).
"""

from __future__ import annotations

from src.features.stats.service_draft import DRAFT_SHRINKAGE_K, _PlayerSeason, project_value


def _ps(season_id: int, avg: float, games: int, minutes: int | None = None) -> _PlayerSeason:
    return _PlayerSeason(
        slug="p",
        display_name="P",
        position="MED",
        season_id=season_id,
        season_name=str(season_id),
        games=games,
        games_45min=games,
        avg_pts=avg,
        total_pts=avg * games,
        std_pts=1.0,
        marca_avg=None,
        as_avg=None,
        goals=0,
        assists=0,
        minutes=minutes if minutes is not None else games * 90,
        second_half_avg=0.0,
        team_name="T",
        photo_path=None,
        player_id=1,
        penalty_goals=0,
        penalties_missed=0,
    )


def test_no_history_uses_current_only() -> None:
    current = _ps(8, avg=5.0, games=6)
    out = project_value(hist=[], current=current, k=DRAFT_SHRINKAGE_K)
    assert out.ensemble_score == 5.0
    assert out.weight_current == 1.0


def test_weight_follows_n_over_n_plus_k() -> None:
    # career prediction high (8.0), current low (2.0): the blend must land
    # between them, weighted by n/(n+k).
    hist = [_ps(6, avg=8.0, games=30), _ps(7, avg=8.0, games=30)]
    current = _ps(8, avg=2.0, games=6)
    k = 4
    out = project_value(hist=hist, current=current, k=k)
    w = 6 / (6 + k)  # 0.6
    assert abs(out.weight_current - w) < 1e-9
    # career ensemble of two flat 8.0 seasons is ~8.0; blended toward 2.0.
    expected = out.career_ensemble * (1 - w) + 2.0 * w
    assert abs(out.ensemble_score - expected) < 1e-6
    assert 2.0 < out.ensemble_score < out.career_ensemble


def test_more_current_games_shifts_weight_to_current() -> None:
    hist = [_ps(7, avg=8.0, games=30)]
    few = project_value(hist=hist, current=_ps(8, 2.0, games=4), k=4)
    many = project_value(hist=hist, current=_ps(8, 2.0, games=8), k=4)
    # More current games -> more weight on the (low) current avg -> lower blend.
    assert many.weight_current > few.weight_current
    assert many.ensemble_score < few.ensemble_score


def test_k_zero_is_current_only_when_history_exists() -> None:
    hist = [_ps(7, avg=8.0, games=30)]
    out = project_value(hist=hist, current=_ps(8, 2.0, games=6), k=0)
    # w = n/(n+0) = 1 -> pure current.
    assert out.weight_current == 1.0
    assert abs(out.ensemble_score - 2.0) < 1e-9
