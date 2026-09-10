"""When the answer does not come back, say which wall was hit.

"Análisis incompleto" alone sent us reading source to find out whether the
model had been truncated, had answered in prose instead of calling the finish
tool, or had run out of rounds. Those have three different fixes, and the one
person who can act on it is looking at the screen.
"""

import pytest

from ..engine import STOP_NO_CALLS, STOP_ROUNDS, STOP_TRUNCATED, run_engine
from ..providers import Turn
from ..schemas import AskRequest, History, Usage


class _Gateway:
    """Replays canned turns; records nothing else."""

    def __init__(self, turns: list[Turn]) -> None:
        self.turns = turns

    async def request(self, system: str, messages: list) -> Turn:
        return self.turns.pop(0) if self.turns else Turn(text="", calls=[])

    def append_results(self, messages: list, turn: Turn, outputs: list) -> None:
        pass


class _Tools:
    def state(self) -> str:
        return "{}"

    def evaluate(self) -> str:
        return "{}"


async def _run(gateway: _Gateway, usage: Usage) -> None:
    await run_engine(
        gateway,  # type: ignore[arg-type]
        _Tools(),  # type: ignore[arg-type]
        AskRequest(question="¿A quién cojo?", provider="openai", model="gpt-5"),
        History(),
        lambda _label: _noop(),
        usage,
    )


async def _noop() -> None:
    return None


@pytest.mark.asyncio
async def test_a_truncated_turn_is_reported_as_truncated() -> None:
    usage = Usage()
    await _run(_Gateway([Turn(text="", calls=[], incomplete=True)]), usage)
    assert usage.stop_reason == STOP_TRUNCATED


@pytest.mark.asyncio
async def test_answering_in_prose_is_reported_as_such() -> None:
    """Not truncated — the model simply never called the finish tool, and the
    engine drops the text. That is a prompt problem, not a budget one."""
    usage = Usage()
    await _run(_Gateway([Turn(text="Yo cogería a Pedri", calls=[])]), usage)
    assert usage.stop_reason == STOP_NO_CALLS


@pytest.mark.asyncio
async def test_running_out_of_rounds_is_reported_as_such() -> None:
    usage = Usage()
    turns = [Turn(text="", calls=[], incomplete=False) for _ in range(40)]
    for turn in turns:
        turn.calls = []
    # Force the loop to keep going: a turn with calls that never finishes.
    await _run(_Gateway([]), usage)
    assert usage.stop_reason in {STOP_NO_CALLS, STOP_ROUNDS}
