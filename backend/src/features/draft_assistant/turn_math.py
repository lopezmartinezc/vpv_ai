"""Projecting the snake order forward.

The single most useful thing an assistant can tell you mid-draft is whether a
player will still be there when you pick again — and that depends entirely on
how many picks separate your turns. In a snake that gap is wildly uneven: the
participant at the turn picks twice in a row, the one at the top of the order
waits almost two full rounds.

The snake rule itself is not reimplemented here; this builds on
``_get_participant_for_pick`` in the drafts service so there is one definition
of whose turn it is.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.features.drafts.service import _get_participant_for_pick

# How far ahead we are willing to project. A full draft is 26 rounds; nobody
# needs to reason past a couple of them.
MAX_LOOKAHEAD = 200


@dataclass(frozen=True)
class UpcomingPick:
    pick_number: int
    round_number: int
    participant_id: int


def upcoming_picks(
    next_pick: int,
    draft_type: str,
    ordered_ids: list[int],
    count: int,
) -> list[UpcomingPick]:
    """The next ``count`` picks starting at ``next_pick``, in order."""
    n = len(ordered_ids)
    if n == 0 or count <= 0:
        return []
    out: list[UpcomingPick] = []
    for pick in range(next_pick, next_pick + min(count, MAX_LOOKAHEAD)):
        out.append(
            UpcomingPick(
                pick_number=pick,
                round_number=(pick - 1) // n + 1,
                participant_id=_get_participant_for_pick(pick, draft_type, ordered_ids),
            )
        )
    return out


def next_pick_for(
    participant_id: int,
    after_pick: int,
    draft_type: str,
    ordered_ids: list[int],
) -> int | None:
    """The next pick number belonging to ``participant_id`` strictly after
    ``after_pick``. None if they are not in the order.

    Scans rather than solving in closed form: the search is bounded by two
    rounds (a participant always picks at least once per round) and this way the
    snake rule stays in exactly one place.
    """
    n = len(ordered_ids)
    if n == 0 or participant_id not in ordered_ids:
        return None
    for pick in range(after_pick + 1, after_pick + 2 * n + 1):
        if _get_participant_for_pick(pick, draft_type, ordered_ids) == participant_id:
            return pick
    return None
