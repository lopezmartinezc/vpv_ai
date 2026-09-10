"""The bootstrap evidence should not be paid for twice, nor grow without bound.

The engine already hands the model the draft state and the evaluation in the
first message. If the model then asks for `estado_draft` again it must get the
"repeated" reply, not another ten thousand tokens of the same thing. And the
state itself listed every pick by name: 286 rows by the end of a draft, resent
on every round, when `plantillas` already answers "who has whom".
"""

import json

import pytest

from ..engine import run_engine
from ..providers import Call, Turn
from ..schemas import AskRequest, History, Usage, ViewContext
from ..tools import Toolset
from .factories import pick, snapshot


class _Gateway:
    def __init__(self, turns: list[Turn]) -> None:
        self.turns = turns
        self.outputs: list[tuple[Call, str]] = []

    async def request(self, system: str, messages: list) -> Turn:
        return self.turns.pop(0)

    def append_results(self, messages: list, turn: Turn, outputs: list) -> None:
        self.outputs.extend(outputs)


async def _noop(_: str) -> None:
    return None


@pytest.mark.asyncio
async def test_asking_for_the_bootstrap_again_is_a_repeat() -> None:
    final_args = json.dumps({"explanation": "ok", "player_ids": [], "evidence_ids": ["state"]})
    gateway = _Gateway(
        [
            Turn(calls=[Call(id="1", name="estado_draft", arguments="{}")]),
            Turn(calls=[Call(id="2", name="responder", arguments=final_args)]),
        ]
    )
    await run_engine(
        gateway,  # type: ignore[arg-type]
        Toolset(snapshot(), 11, ViewContext()),
        AskRequest(question="q", provider="openai", model="m"),
        History(),
        _noop,
        Usage(),
    )
    assert gateway.outputs and "repetida" in gateway.outputs[0][1]


def test_state_summarises_picks_instead_of_listing_them_all() -> None:
    data = snapshot()
    data.draft.picks = [pick(i, i, 4) for i in range(1, 31)]
    state = json.loads(Toolset(data, 11, ViewContext()).state())["data"]
    assert state["total_picks"] == 30
    assert len(state["recent_picks"]) <= 12
    # Zero entries included on purpose: "who has not picked yet" is part of
    # where the draft stands.
    assert state["picks_by_participant"] == {"1": 30, "2": 0}
    assert "picks" not in state
    # The round the draft is in is still there — that is what "how early do
    # keepers go" reasoning needs, not every name.
    assert state["current_round"] >= 1
