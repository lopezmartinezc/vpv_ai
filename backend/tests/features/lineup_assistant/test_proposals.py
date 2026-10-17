"""The chat's proposals come back structured, checked by the server.

"Pon a Puado por Raphinha" used to be words only; the user had to redo it by
hand. Now a proposal is the resulting eleven (ids, formation, who enters and
leaves against what is on screen), built on the server from the asker's own
squad and the valid formations, so the screen can apply it in one click and
the model cannot propose what the rules refuse.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.features.lineup_assistant.optimizer import Formation
from src.features.lineup_assistant.proposals import ProposalError, swap

FORMATIONS = [Formation("1-4-3-3", 4, 3, 3), Formation("1-4-4-2", 4, 4, 2)]


def sp(pid: int, name: str, position: str) -> SimpleNamespace:
    return SimpleNamespace(player_id=pid, display_name=name, position=position)


SQUAD = [
    sp(1, "Joan Garcia", "POR"),
    sp(2, "Ezkieta", "POR"),
    *(sp(10 + i, f"Defensa {i}", "DEF") for i in range(5)),
    *(sp(20 + i, f"Medio {i}", "MED") for i in range(5)),
    *(sp(30 + i, f"Delantero {i}", "DEL") for i in range(4)),
]
BASE_433 = [1, 10, 11, 12, 13, 20, 21, 22, 30, 31, 32]


def test_a_like_for_like_swap_keeps_the_formation() -> None:
    p = swap(BASE_433, entering=[33], leaving=[32], squad=SQUAD, formations=FORMATIONS, basis="b")
    assert p.formation == "1-4-3-3"
    assert [x.player_id for x in p.players] == [1, 10, 11, 12, 13, 20, 21, 22, 30, 31, 33]
    assert p.entering == ["Delantero 3"]
    assert p.leaving == ["Delantero 2"]
    assert p.basis == "b"


def test_a_swap_across_positions_finds_the_new_formation() -> None:
    p = swap(BASE_433, entering=[23], leaving=[32], squad=SQUAD, formations=FORMATIONS, basis="")
    assert p.formation == "1-4-4-2"


def test_a_swap_that_fits_no_formation_is_refused() -> None:
    with pytest.raises(ProposalError, match="formacion"):
        swap(BASE_433, entering=[14], leaving=[32], squad=SQUAD, formations=FORMATIONS, basis="")


def test_two_goalkeepers_are_refused() -> None:
    with pytest.raises(ProposalError, match="portero"):
        swap(BASE_433, entering=[2], leaving=[32], squad=SQUAD, formations=FORMATIONS, basis="")


def test_leaving_someone_not_on_the_pitch_is_refused() -> None:
    with pytest.raises(ProposalError, match="no esta"):
        swap(BASE_433, entering=[33], leaving=[14], squad=SQUAD, formations=FORMATIONS, basis="")


def test_entering_someone_already_on_the_pitch_is_refused() -> None:
    with pytest.raises(ProposalError, match="ya esta"):
        swap(BASE_433, entering=[30], leaving=[32], squad=SQUAD, formations=FORMATIONS, basis="")


def test_a_stranger_is_refused() -> None:
    with pytest.raises(ProposalError, match="plantilla"):
        swap(BASE_433, entering=[99], leaving=[32], squad=SQUAD, formations=FORMATIONS, basis="")


def test_an_incomplete_base_says_how_many_are_missing() -> None:
    with pytest.raises(ProposalError, match="faltan 2"):
        swap(BASE_433[:9], entering=[], leaving=[], squad=SQUAD, formations=FORMATIONS, basis="")


def test_from_an_empty_base_eleven_entries_make_an_eleven() -> None:
    p = swap([], entering=BASE_433, leaving=[], squad=SQUAD, formations=FORMATIONS, basis="")
    assert p.formation == "1-4-3-3"
    assert len(p.entering) == 11
    assert p.leaving == []


# --- the whole turn: tool → context → response -------------------------------

from typing import Any  # noqa: E402

from src.features.lineup_assistant.context import LineupContext  # noqa: E402
from src.features.lineup_assistant.schemas import LineupDraft, LineupDraftSlot  # noqa: E402
from src.features.lineup_assistant.service import LineupAssistantService  # noqa: E402
from src.shared.assistant.endpoint import reply_payload  # noqa: E402
from src.shared.assistant.providers.base import AssistantReply  # noqa: E402
from src.shared.assistant.tools import run_tool  # noqa: E402


class SwappingProvider:
    """Asks proponer_cambios for Delantero 3 in, Delantero 2 out."""

    name = "fake"
    model = "fake-1"

    async def run(self, *, system: str, messages: Any, tools: Any, on_progress: Any = None):
        text = await run_tool(
            tools, "proponer_cambios", {"entran": ["Delantero 3"], "salen": ["Delantero 2"]}
        )
        return AssistantReply(text=text)


@pytest.fixture
def my_squad(monkeypatch: pytest.MonkeyPatch) -> None:
    async def squad(self: LineupContext) -> SimpleNamespace:
        return SimpleNamespace(squad=SQUAD, current_lineup=None)

    async def formations(self: LineupContext) -> list[Formation]:
        return FORMATIONS

    monkeypatch.setattr(LineupContext, "squad", squad)
    monkeypatch.setattr(LineupContext, "formations", formations)


async def test_a_change_asked_in_the_chat_comes_back_as_a_proposal(my_squad: None) -> None:
    draft = LineupDraft(
        formation="1-4-3-3",
        players=[
            LineupDraftSlot(player_id=i, position_slot=p.position)
            for i, p in ((i, next(s for s in SQUAD if s.player_id == i)) for i in BASE_433)
        ],
    )
    reply = await LineupAssistantService(session=None).ask(  # type: ignore[arg-type]
        season_id=7,
        matchday=6,
        question="Pon a Delantero 3 por Delantero 2",
        user_id=11,
        draft=draft,
        provider=SwappingProvider(),
    )
    assert "Once resultante (1-4-3-3)" in reply.text
    assert "aplicarlo al borrador" in reply.text
    payload = reply_payload(reply)
    proposal = payload["proposal"]
    assert isinstance(proposal, dict)
    assert proposal["formation"] == "1-4-3-3"
    assert proposal["entering"] == ["Delantero 3"]
    assert proposal["leaving"] == ["Delantero 2"]
    assert len(proposal["players"]) == 11


async def test_without_a_change_there_is_no_proposal(my_squad: None) -> None:
    class Talker:
        name = "fake"
        model = "fake-1"

        async def run(self, **kwargs: Any) -> AssistantReply:
            return AssistantReply(text="hola")

    reply = await LineupAssistantService(session=None).ask(  # type: ignore[arg-type]
        season_id=7, matchday=6, question="hola", user_id=11, provider=Talker()
    )
    assert "proposal" not in reply_payload(reply)
