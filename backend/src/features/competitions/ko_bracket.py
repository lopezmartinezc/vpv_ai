"""Pure KO bracket helpers — building blocks reused by format plugins.

A plugin describes its KO shape with these helpers and the engine
materialises them into ``competition_matchups`` rows. No DB, no
mutation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KoSlot:
    """A single KO matchup before materialisation.

    Either ``a_pid`` / ``b_pid`` are set directly (for the first KO
    round whose participants come from standings) or ``feeder_a`` /
    ``feeder_b`` reference *indices into the same KO slot list* whose
    winners will fill the seats once resolved.
    """

    round_number: int
    round_label: str  # 'semi' | 'final' | 'quarter' | ...
    a_pid: int | None = None
    b_pid: int | None = None
    feeder_a: int | None = None  # index of upstream KoSlot in the list
    feeder_b: int | None = None


def seed_classic_bracket(
    top_n_pids: list[int], round_label: str, round_number: int
) -> list[KoSlot]:
    """Seed a bracket where best meets worst, etc.

    For ``top_n=4``: ``[1º vs 4º, 2º vs 3º]`` (2 cruces).
    For ``top_n=8``: ``[1-8, 4-5, 2-7, 3-6]`` (4 cruces).
    The order matters: the next round pairs slot[0]↔slot[1],
    slot[2]↔slot[3] etc., which keeps top seeds on opposite sides of
    the bracket.
    """
    n = len(top_n_pids)
    if n == 4:
        return [
            KoSlot(round_number, round_label, top_n_pids[0], top_n_pids[3]),
            KoSlot(round_number, round_label, top_n_pids[1], top_n_pids[2]),
        ]
    if n == 8:
        return [
            KoSlot(round_number, round_label, top_n_pids[0], top_n_pids[7]),
            KoSlot(round_number, round_label, top_n_pids[3], top_n_pids[4]),
            KoSlot(round_number, round_label, top_n_pids[1], top_n_pids[6]),
            KoSlot(round_number, round_label, top_n_pids[2], top_n_pids[5]),
        ]
    raise ValueError(f"seed_classic_bracket only supports top_n in {{4, 8}}, got {n}")


def chain_winners(
    feeders: list[KoSlot],
    round_number: int,
    round_label: str,
    feeder_offset: int,
) -> list[KoSlot]:
    """Build the next KO round whose seats are filled by the winners
    of the previous round.

    Pairs adjacent feeder slots: feeders[0] vs feeders[1],
    feeders[2] vs feeders[3], etc. Always produces ``len(feeders) // 2``
    new slots. ``feeder_offset`` is added to every index so the caller
    can compose multi-round brackets in a single flat list.
    """
    if len(feeders) % 2 != 0:
        raise ValueError(f"chain_winners needs an even number of feeders, got {len(feeders)}")
    out: list[KoSlot] = []
    for i in range(0, len(feeders), 2):
        out.append(
            KoSlot(
                round_number=round_number,
                round_label=round_label,
                feeder_a=feeder_offset + i,
                feeder_b=feeder_offset + i + 1,
            )
        )
    return out
