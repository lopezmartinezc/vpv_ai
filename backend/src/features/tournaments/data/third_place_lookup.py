"""Lookup helper for FIFA World Cup 2026 best-3rd-placed combinations.

Annexe C of the FIFA WC 2026 regulations lists 495 possible combinations
of which 8 of the 12 third-placed teams advance to the round of 32, and
which group's 3rd-placed team feeds each of the 8 R32 slots that take a
"Best 3rd of X" team.

When the group stage finishes, you call ``resolve_third_place_assignments``
with the set of 8 group letters whose 3rd-placed teams advance, and you
get back a mapping ``match_code -> "3X"`` for the 8 placeholder slots.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "fifa_wc_2026_third_place_combinations.json"


@lru_cache(maxsize=1)
def _combinations() -> dict[int, dict[str, str]]:
    """Load and cache the 495-row lookup table."""
    with _DATA_PATH.open() as f:
        return {int(k): v for k, v in json.load(f).items()}


def resolve_third_place_assignments(
    qualifying_groups: set[str],
) -> dict[str, str] | None:
    """Return the M74..M87 -> '3X' mapping for the given set of qualifying groups.

    ``qualifying_groups`` must be a set of exactly 8 group letters in {A..L}.

    Returns the dict for the matching Annexe C row, or ``None`` if no row
    matches (i.e. malformed input).
    """
    if len(qualifying_groups) != 8:
        return None
    target_letters = {g.upper() for g in qualifying_groups}
    for row in _combinations().values():
        row_letters = {v[1] for v in row.values()}  # strip leading "3"
        if row_letters == target_letters:
            return dict(row)
    return None
