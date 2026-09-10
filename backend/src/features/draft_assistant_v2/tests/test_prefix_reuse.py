"""Two questions at the same draft state must share everything but the question.

Providers cache on exact prefix. Measured in production, history cleared, two
questions back to back at one pick: 7,936 cached tokens on the first and
7,936 on the second — not one token of the bootstrap reused across questions,
for two reasons an earlier fix missed. The history sits before the last
message, so evidence placed there is never at the same position twice; and
the bootstrap carried the snapshot's capture time, so it was never byte-equal
anyway.

The bootstrap now lives in the system prompt, ahead of tools and history, and
carries no clock. This test is the structural version of the experiment: same
snapshot, different questions, identical prefix.
"""

import json

import pytest

from ..engine import run_engine
from ..providers import Turn
from ..schemas import AskRequest, History, Usage, ViewContext
from ..snapshot import Snapshot
from ..tools import Toolset
from .factories import snapshot


class _Gateway:
    def __init__(self) -> None:
        self.system = ""
        self.messages: list[dict] = []

    async def request(self, system: str, messages: list) -> Turn:
        self.system = system
        self.messages = [dict(m) for m in messages]
        return Turn(calls=[])

    def append_results(self, messages: list, turn: Turn, outputs: list) -> None:
        pass


async def _noop(_: str) -> None:
    return None


async def _ask(question: str, data: Snapshot | None = None) -> _Gateway:
    gateway = _Gateway()
    await run_engine(
        gateway,  # type: ignore[arg-type]
        Toolset(data or snapshot(), 11, ViewContext()),
        AskRequest(question=question, provider="openai", model="m"),
        History(),
        _noop,
        Usage(),
    )
    return gateway


@pytest.mark.asyncio
async def test_same_state_different_questions_share_the_whole_prefix() -> None:
    first = await _ask("¿A quién cojo?")
    second = await _ask("¿Y de portero?")
    assert first.system == second.system
    assert first.messages[:-1] == second.messages[:-1]
    assert first.messages[-1]["content"] == "¿A quién cojo?"
    assert second.messages[-1]["content"] == "¿Y de portero?"


@pytest.mark.asyncio
async def test_the_evidence_lives_in_the_system_prompt() -> None:
    gateway = await _ask("q")
    assert "EVIDENCIA ACTUAL DEL SERVIDOR" in gateway.system
    assert '"evidence_id": "state"' in gateway.system
    assert '"evidence_id": "evaluation"' in gateway.system
    assert "EVIDENCIA" not in gateway.messages[-1]["content"]


@pytest.mark.asyncio
async def test_the_evidence_carries_no_clock() -> None:
    """A capture timestamp would make every bootstrap unique — a cache miss on
    every question even with nothing else changed."""
    data = snapshot()
    state = json.loads(Toolset(data, 11, ViewContext()).state())["data"]
    assert "at" not in state["revision"]
    assert data.captured_at not in json.dumps(state)


@pytest.mark.asyncio
async def test_a_changed_draft_changes_the_prefix() -> None:
    """The flip side: reuse must stop exactly when the state moved."""
    from .factories import pick

    before = await _ask("q")
    changed = snapshot()
    changed.draft.picks = [pick()]
    after = await _ask("q", changed)
    assert before.system != after.system


@pytest.mark.asyncio
async def test_the_mode_line_comes_after_the_evidence() -> None:
    """Quick and detailed questions at the same state still share the evidence;
    only the trailing mode line differs."""
    gateway = await _ask("q")
    assert gateway.system.index("EVIDENCIA ACTUAL DEL SERVIDOR") < gateway.system.rindex(
        "Respuesta breve"
    )
