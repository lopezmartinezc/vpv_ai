"""The best-of-three final follows the rules agreed for the Liga playoffs."""

from __future__ import annotations

from src.features.competitions.ko_series import Leg, resolve_best_of_three


def legs(*scores: tuple[int, int] | None) -> list[Leg]:
    return [
        Leg(
            matchup_id=i,
            matchday_number=19 + i,
            score_a=s[0] if s else None,
            score_b=s[1] if s else None,
        )
        for i, s in enumerate(scores)
    ]


def results(series) -> list[str]:  # type: ignore[no-untyped-def]
    return [o.result for o in series.legs]


def test_two_straight_wins_settle_it_and_the_third_is_not_played() -> None:
    s = resolve_best_of_three(legs((60, 50), (55, 40), (30, 90)), better_seed="b")
    assert (s.wins_a, s.wins_b, s.winner) == (2, 0, "a")
    assert results(s) == ["a", "a", "not_needed"]


def test_nothing_is_settled_before_the_legs_are_scored() -> None:
    s = resolve_best_of_three(legs(None, None, None), better_seed="a")
    assert (s.wins_a, s.wins_b, s.winner) == (0, 0, None)
    assert results(s) == ["pending"] * 3
    one_each = resolve_best_of_three(legs((60, 50), (40, 55), None), better_seed="a")
    assert (one_each.winner, results(one_each)) == (None, ["a", "b", "pending"])


def test_two_one_goes_to_the_third() -> None:
    s = resolve_best_of_three(legs((60, 50), (40, 55), (70, 69)), better_seed="b")
    assert (s.wins_a, s.wins_b, s.winner) == (2, 1, "a")
    assert [o.decided_by for o in s.legs] == ["points"] * 3


def test_a_drawn_third_goes_to_the_better_difference_of_the_other_two() -> None:
    # A wins the first by 3, B the second by 10: B is +7 over those two.
    s = resolve_best_of_three(legs((53, 50), (40, 50), (50, 50)), better_seed="a")
    assert (s.wins_a, s.wins_b, s.winner) == (1, 2, "b")
    assert (s.legs[2].result, s.legs[2].decided_by) == ("b", "difference")


def test_a_draw_always_takes_the_final_to_its_third() -> None:
    waiting = resolve_best_of_three(legs((60, 50), (45, 45), None), better_seed="a")
    assert (waiting.winner, results(waiting)) == (None, ["a", "pending", "pending"])

    # A wins the third too: two straight wins, champion.
    a_again = resolve_best_of_three(legs((60, 50), (45, 45), (52, 50)), better_seed="b")
    assert a_again.winner == "a"

    # B wins the third: the draw looks at the first and the third, +10 -2 for A.
    b_third = resolve_best_of_three(legs((60, 50), (45, 45), (48, 50)), better_seed="b")
    assert (b_third.legs[1].result, b_third.legs[1].decided_by) == ("a", "difference")
    assert (b_third.wins_a, b_third.wins_b, b_third.winner) == (2, 1, "a")

    # Same, but B wins the third by more: the drawn second is B's.
    b_more = resolve_best_of_three(legs((60, 50), (45, 45), (40, 60)), better_seed="a")
    assert (b_more.wins_a, b_more.wins_b, b_more.winner) == (1, 2, "b")


def test_level_everywhere_goes_to_the_better_seed() -> None:
    s = resolve_best_of_three(legs((50, 50), (40, 40), (61, 61)), better_seed="b")
    assert (s.wins_a, s.wins_b, s.winner) == (0, 3, "b")
    assert {o.decided_by for o in s.legs} == {"seed"}
    # A drawn leg whose other two cancel out: the seed decides it.
    cancel = resolve_best_of_three(legs((60, 50), (50, 60), (45, 45)), better_seed="a")
    assert (cancel.legs[2].result, cancel.legs[2].decided_by, cancel.winner) == ("a", "seed", "a")
