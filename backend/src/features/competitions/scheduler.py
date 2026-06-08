"""Pure scheduling algorithms — reusable building blocks for format plugins.

Each function is deterministic given the same ``seed``; the format
plugin decides which one to call and with which parameters. No DB
access, no side effects.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Pair:
    """A single head-to-head cruce between two participant ids."""

    a: int
    b: int


def generate_balanced_schedule(
    participants: list[int],
    *,
    n_rounds: int = 6,
    games_per_player: int = 4,
    seed: int = 0,
    max_attempts: int = 50,
) -> list[list[Pair]]:
    """Return a calendar where EVERY participant plays exactly
    ``games_per_player`` cruces over ``n_rounds`` jornadas.

    For 13 participants, ``n_rounds=6``, ``games_per_player=4``:
    - Total cruces = 13 * 4 / 2 = 26.
    - Round sizes: [5, 5, 5, 5, 3, 3].
    - Each participant rests 2 times.

    Algorithm:
    1. Place participants on a circle in shuffled order.
    2. Build the 4-regular circulant graph C(n; {1, 4}) over that
       circle. Each vertex connects to ±1 and ±4 mod n; that's
       exactly 4 neighbours per node.
    3. Greedy edge-colouring into ``n_rounds`` matchings whose sizes
       hit the target distribution.
    4. Sanity-check that every participant appears
       ``games_per_player`` times. Retry with a new seed if not.

    Raises ``RuntimeError`` if no valid schedule is found within
    ``max_attempts`` seeds (extremely unlikely with the chosen
    parameters but guarded so we surface the problem instead of
    looping forever).
    """
    n = len(participants)
    if n != 13 or games_per_player != 4 or n_rounds != 6:
        # Generalising the circulant + distribution to other sizes is
        # out of scope for v1; future formats can add their own
        # scheduler functions next to this one.
        raise NotImplementedError(
            "generate_balanced_schedule is tuned for 13 / 4 / 6. "
            "Add a dedicated function for other shapes."
        )

    target_sizes = [5, 5, 5, 5, 3, 3]
    assert sum(target_sizes) == n * games_per_player // 2

    rng = random.Random(seed)
    for _attempt in range(max_attempts):
        attempt_rng = random.Random(rng.random())
        rotated = participants[:]
        attempt_rng.shuffle(rotated)

        # Build edges via circulant C(n; {1, 4}) over the rotated order.
        edges: list[Pair] = []
        for i in range(n):
            for d in (1, 4):
                j = (i + d) % n
                a, b = rotated[i], rotated[j]
                if a < b:
                    edges.append(Pair(a, b))
                else:
                    edges.append(Pair(b, a))
        edges = list({(p.a, p.b): p for p in edges}.values())
        # Expect 26 distinct edges.
        if len(edges) != n * games_per_player // 2:
            continue  # try another shuffle

        attempt_rng.shuffle(edges)
        pending = edges[:]
        rounds: list[list[Pair]] = []

        for target in target_sizes:
            used: set[int] = set()
            round_pairs: list[Pair] = []
            for pair in pending[:]:
                if len(round_pairs) >= target:
                    break
                if pair.a in used or pair.b in used:
                    continue
                round_pairs.append(pair)
                used.update([pair.a, pair.b])
                pending.remove(pair)
            if len(round_pairs) != target:
                break  # greedy stuck on this attempt
            rounds.append(round_pairs)

        if len(rounds) != n_rounds or pending:
            continue

        # Sanity check: every participant must appear ``games_per_player`` times.
        counts: dict[int, int] = {pid: 0 for pid in participants}
        for rnd in rounds:
            for pair in rnd:
                counts[pair.a] += 1
                counts[pair.b] += 1
        if all(c == games_per_player for c in counts.values()):
            return rounds

    raise RuntimeError(
        f"generate_balanced_schedule did not converge in {max_attempts} attempts "
        f"with seed={seed}. Bug in the algorithm or wildly unlucky."
    )


def generate_berger(participants: list[int]) -> list[list[Pair | None]]:
    """Classic round-robin Berger schedule.

    Returns a list of rounds. Each round is a list of pairs; entries
    of ``None`` represent the bye position (caller can derive who
    rests). With an odd number of participants the algorithm appends a
    virtual ``BYE`` slot.

    Currently unused by ``balanced_ko4`` but provided as a reusable
    building block for future ``berger_*`` plugins (see plan).
    """
    pids = list(participants)
    bye = -1
    if len(pids) % 2 == 1:
        pids.append(bye)
    n = len(pids)
    fixed = pids[0]
    rot = pids[1:]

    rounds: list[list[Pair | None]] = []
    for _ in range(n - 1):
        raw: list[tuple[int, int]] = [(fixed, rot[-1])]
        for i in range(n // 2 - 1):
            raw.append((rot[i], rot[-2 - i]))
        round_pairs: list[Pair | None] = []
        for a, b in raw:
            if a == bye or b == bye:
                round_pairs.append(None)
            else:
                lo, hi = (a, b) if a < b else (b, a)
                round_pairs.append(Pair(lo, hi))
        rounds.append(round_pairs)
        rot = [rot[-1], *rot[:-1]]
    return rounds
