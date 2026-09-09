"""Snake turn projection: who picks next, and how long until you pick again.

This is what answers "can I wait for this player?" — the gap between your turns
is the whole question in a snake draft, and it is very uneven: at the turn you
pick twice in a row, in the middle you wait almost two full rounds.
"""

from __future__ import annotations

from src.features.draft_assistant.turn_math import next_pick_for, upcoming_picks

# Four participants, draft order 1..4.
IDS = [10, 20, 30, 40]


def test_snake_first_round_goes_forward() -> None:
    picks = upcoming_picks(1, "snake", IDS, count=4)
    assert [p.participant_id for p in picks] == [10, 20, 30, 40]
    assert [p.round_number for p in picks] == [1, 1, 1, 1]


def test_snake_second_round_reverses() -> None:
    picks = upcoming_picks(5, "snake", IDS, count=4)
    assert [p.participant_id for p in picks] == [40, 30, 20, 10]
    assert [p.round_number for p in picks] == [2, 2, 2, 2]


def test_linear_never_reverses() -> None:
    picks = upcoming_picks(5, "linear", IDS, count=4)
    assert [p.participant_id for p in picks] == [10, 20, 30, 40]


def test_pick_numbers_are_absolute() -> None:
    picks = upcoming_picks(7, "snake", IDS, count=3)
    assert [p.pick_number for p in picks] == [7, 8, 9]


def test_turn_participant_picks_back_to_back() -> None:
    """At the turn of a snake, the last of round 1 is also first of round 2.

    Participant 40 picks at #4 and #5 — a one-pick gap. Anyone advising on
    whether to wait must know this, or they will tell you to wait when you
    actually get two picks in a row.
    """
    assert next_pick_for(40, after_pick=4, draft_type="snake", ordered_ids=IDS) == 5


def test_first_participant_waits_almost_two_rounds() -> None:
    """Participant 10 picks at #1 and not again until #8 — six picks pass."""
    assert next_pick_for(10, after_pick=1, draft_type="snake", ordered_ids=IDS) == 8


def test_linear_gap_is_always_one_round() -> None:
    assert next_pick_for(10, after_pick=1, draft_type="linear", ordered_ids=IDS) == 5
    assert next_pick_for(40, after_pick=4, draft_type="linear", ordered_ids=IDS) == 8


def test_unknown_participant_has_no_next_pick() -> None:
    assert next_pick_for(99, after_pick=1, draft_type="snake", ordered_ids=IDS) is None


def test_no_participants_is_not_a_crash() -> None:
    assert upcoming_picks(1, "snake", [], count=5) == []
    assert next_pick_for(10, after_pick=1, draft_type="snake", ordered_ids=[]) is None
