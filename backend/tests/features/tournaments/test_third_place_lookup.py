"""Unit tests for the FIFA WC 2026 best-third-placed Annexe C lookup table.

These are pure (no DB). They guard the integrity of
``fifa_wc_2026_third_place_combinations.json`` against the one bug class
that previously shipped: a table whose rows assigned a group's 3rd-placed
team to an R32 slot that — per the official bracket — can never receive
that group. Every slot only accepts thirds from a fixed set of groups, so
any assignment outside that set is provably wrong.
"""

from __future__ import annotations

import itertools

from src.features.tournaments.data.third_place_lookup import (
    _combinations,
    resolve_third_place_assignments,
)

# Official FIFA WC 2026 R32 slots that take a best-third team, and the set
# of groups each slot is allowed to draw from (Annexe / official bracket).
ALLOWED: dict[str, set[str]] = {
    "M74": set("ABCDF"),  # 1E
    "M77": set("CDFGH"),  # 1I
    "M79": set("CEFHI"),  # 1A
    "M80": set("EHIJK"),  # 1L
    "M81": set("BEFIJ"),  # 1D
    "M82": set("AEHIJ"),  # 1G
    "M85": set("EFGIJ"),  # 1B
    "M87": set("DEIJL"),  # 1K
}
SLOTS = list(ALLOWED)


def test_table_has_495_rows() -> None:
    assert len(_combinations()) == 495


def test_every_row_respects_slot_group_constraints() -> None:
    """No row may assign a group's 3rd to a slot that can't receive it."""
    offenders: list[tuple[int, str, str]] = []
    for idx, row in _combinations().items():
        assert set(row.keys()) == set(SLOTS), (idx, row)
        for slot, val in row.items():
            group = val[1]  # strip leading "3"
            if group not in ALLOWED[slot]:
                offenders.append((idx, slot, val))
    assert not offenders, f"slot-constraint violations: {offenders[:10]}"


def test_every_row_is_a_bijection_of_eight_distinct_groups() -> None:
    for idx, row in _combinations().items():
        groups = {v[1] for v in row.values()}
        assert len(groups) == 8, (idx, row)


def test_all_495_combinations_are_unique() -> None:
    keys = {frozenset(v[1] for v in row.values()) for row in _combinations().values()}
    assert len(keys) == 495


def test_resolve_returns_none_for_malformed_input() -> None:
    assert resolve_third_place_assignments(set("ABC")) is None  # too few
    assert resolve_third_place_assignments(set("ABCDEFGHI")) is None  # too many


def test_resolve_known_combination_bdefijkl() -> None:
    """Regression: BDEFIJKL must map to the official Annexe C row.

    Previously the table mis-slotted all eight thirds (e.g. M74 -> 3E,
    which is impossible since slot M74 only accepts A/B/C/D/F).
    """
    mapping = resolve_third_place_assignments(set("BDEFIJKL"))
    assert mapping == {
        "M74": "3D",
        "M77": "3F",
        "M79": "3E",
        "M80": "3K",
        "M81": "3B",
        "M82": "3I",
        "M85": "3J",
        "M87": "3L",
    }


def test_resolve_is_consistent_with_table_for_a_sampling() -> None:
    """resolve() on a row's own group-set returns that same row."""
    for idx, row in itertools.islice(_combinations().items(), 0, 495, 37):
        groups = {v[1] for v in row.values()}
        assert resolve_third_place_assignments(groups) == row, idx
