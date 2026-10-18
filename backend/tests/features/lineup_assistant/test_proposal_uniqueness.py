from types import SimpleNamespace

import pytest

from src.features.lineup_assistant.optimizer import Formation
from src.features.lineup_assistant.proposals import ProposalError, swap


@pytest.mark.parametrize(
    "base,entering,leaving",
    [
        (list(range(11)), [11, 11], [9, 10]),
        (list(range(11)), [11], [10, 10]),
        ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9], [], []),
    ],
)
def test_repeated_ids_are_refused(
    base: list[int], entering: list[int], leaving: list[int]
) -> None:
    positions = ["POR"] + ["DEF"] * 4 + ["MED"] * 3 + ["DEL"] * 4
    squad = [
        SimpleNamespace(player_id=i, display_name=str(i), position=p)
        for i, p in enumerate(positions)
    ]
    with pytest.raises(ProposalError, match="repet"):
        swap(
            base,
            entering=entering,
            leaving=leaving,
            squad=squad,
            formations=[Formation("1-4-3-3", 4, 3, 3)],
            basis="test",
        )
