"""The Liga playoff format: everyone once, then 1-8/4-5/2-7/3-6, then a final
over three jornadas. The other formats keep their shape."""

from __future__ import annotations

from itertools import combinations

import pytest

from src.features.competitions.formats import FORMAT_REGISTRY, get_format
from src.features.competitions.schemas import StandingEntry

BO3 = get_format("liga_berger_ko8_bo3")
PIDS = list(range(101, 112))  # 11 participants
REGULAR_MDS = list(range(1006, 1017))  # 11 matchday ids
KO_MDS = [1017, 1018, 1019, 1020, 1021]


def table(pids: list[int]) -> list[StandingEntry]:
    return [
        StandingEntry(
            rank=i + 1,
            participant_id=pid,
            display_name=f"P{i + 1}",
            played=10,
            wins=0,
            draws=0,
            losses=0,
            rests=1,
            points=30 - i,
            diff_avg=0,
            pts_total_vpv=0,
        )
        for i, pid in enumerate(pids)
    ]


def test_it_is_registered_and_the_old_formats_keep_their_shape() -> None:
    assert set(FORMAT_REGISTRY) == {"balanced_ko4", "liga_berger_ko8", "liga_berger_ko8_bo3"}
    assert (BO3.required_rounds_regular(11), BO3.required_rounds_ko()) == (11, 5)
    assert (BO3.final_legs, BO3.head_to_head_tiebreak) == (3, True)
    old = get_format("liga_berger_ko8")
    assert (old.required_rounds_ko(), old.final_legs, old.head_to_head_tiebreak) == (3, 1, False)
    mundial = get_format("balanced_ko4")
    assert (mundial.final_legs, mundial.head_to_head_tiebreak) == (1, False)


def test_eleven_play_everyone_once_over_eleven_jornadas_resting_once() -> None:
    drafts = BO3.generate_regular_phase(PIDS, REGULAR_MDS, seed=7)
    assert len(drafts) == 55
    pairs = {frozenset((d.participant_a_id, d.participant_b_id)) for d in drafts}
    assert pairs == {frozenset(p) for p in combinations(PIDS, 2)}
    per_round: dict[int, list[int]] = {}
    for d in drafts:
        per_round.setdefault(d.matchday_id, []).extend([d.participant_a_id, d.participant_b_id])  # type: ignore[list-item]
    assert sorted(per_round) == REGULAR_MDS
    for players in per_round.values():
        assert len(players) == 10 and len(set(players)) == 10  # five cruces, one rests
    rests = [pid for pid in PIDS for players in per_round.values() if pid not in players]
    assert sorted(rests) == PIDS  # each rests exactly once


def test_cuartos_semis_and_three_final_jornadas() -> None:
    drafts = BO3.generate_ko_phase(table(PIDS), KO_MDS, n_regular_rounds=11)
    quarters, semis, finals = drafts[:4], drafts[4:6], drafts[6:]
    seed = {pid: i + 1 for i, pid in enumerate(PIDS)}

    assert [(seed[d.participant_a_id], seed[d.participant_b_id]) for d in quarters] == [  # type: ignore[index]
        (1, 8),
        (4, 5),
        (2, 7),
        (3, 6),
    ]
    assert {(d.round_label, d.round_number, d.matchday_id) for d in quarters} == {
        ("quarter", 12, 1017)
    }

    # Winner 1-8 v winner 4-5, winner 2-7 v winner 3-6.
    assert [(d.feeder_a_index, d.feeder_b_index) for d in semis] == [(0, 1), (2, 3)]
    assert {(d.round_label, d.round_number, d.matchday_id) for d in semis} == {("semi", 13, 1018)}

    assert [(d.round_label, d.round_number, d.matchday_id) for d in finals] == [
        ("final", 14, 1019),
        ("final", 15, 1020),
        ("final", 16, 1021),
    ]
    # Every jornada of the final is fed by both semis.
    assert {(d.feeder_a_index, d.feeder_b_index) for d in finals} == {(4, 5)}
    assert all(d.participant_a_id is None and d.participant_b_id is None for d in semis + finals)


def test_the_ko_needs_its_five_jornadas_and_a_clean_cut() -> None:
    with pytest.raises(ValueError, match="5 KO matchdays"):
        BO3.generate_ko_phase(table(PIDS), KO_MDS[:3], n_regular_rounds=11)
    level = table(PIDS)
    level[8] = level[8].model_copy(update={"rank": 8})  # 8th and 9th level
    with pytest.raises(ValueError, match="Empate"):
        BO3.generate_ko_phase(level, KO_MDS, n_regular_rounds=11)
