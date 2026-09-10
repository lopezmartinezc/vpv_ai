"""Evidence before the question, so consecutive questions share a cached prefix.

The bootstrap (draft state + evaluation) is identical for every question asked
at the same draft revision; the question is what changes. Providers cache on
exact prefix, so with the question first the cache stops right before the
evidence on every new question. Evidence first puts it inside the reusable
prefix — and leaves the question at the end, next to generation, where a long
context serves it best.

Measured on the first quick-mode answer after caching was surfaced: 4,608 of
9,908 input tokens cached. The bootstrap was on the wrong side of the cut.
"""

import pytest

from ..engine import run_engine
from ..providers import Turn
from ..schemas import AskRequest, History, Usage, ViewContext
from ..tools import Toolset
from .factories import snapshot


class _Gateway:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def request(self, system: str, messages: list) -> Turn:
        self.sent = [dict(m) for m in messages]
        return Turn(calls=[])

    def append_results(self, messages: list, turn: Turn, outputs: list) -> None:
        pass


async def _noop(_: str) -> None:
    return None


@pytest.mark.asyncio
async def test_the_last_message_puts_evidence_before_the_question() -> None:
    gateway = _Gateway()
    await run_engine(
        gateway,  # type: ignore[arg-type]
        Toolset(snapshot(), 11, ViewContext()),
        AskRequest(question="¿A quién cojo?", provider="openai", model="m"),
        History(),
        _noop,
        Usage(),
    )
    content = gateway.sent[-1]["content"]
    assert isinstance(content, str)
    assert content.index("EVIDENCIA ACTUAL DEL SERVIDOR") < content.index("¿A quién cojo?")
    assert content.rstrip().endswith("¿A quién cojo?")
