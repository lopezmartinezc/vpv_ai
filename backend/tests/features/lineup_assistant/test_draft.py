"""The chat sees the eleven being edited, not only the one saved.

The request carried question and history; the tools read the saved lineup.
Asking "revisa este once" about an eleven not yet sent got an answer about
the previous one. Now the screen sends its draft with the question, the
server checks it against the asker's own squad (ids, positions, duplicates)
and the model is told which is the draft and which is saved.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.core.exceptions import BusinessRuleError
from src.features.lineup_assistant.draft import draft_text, validate_draft
from src.features.lineup_assistant.schemas import LineupDraft, LineupDraftSlot
from src.features.lineup_assistant.service import LineupAssistantService
from src.shared.assistant.providers.base import AssistantReply


def squad_player(pid: int, name: str, position: str) -> SimpleNamespace:
    return SimpleNamespace(player_id=pid, display_name=name, position=position, team_name="T")


SQUAD = [
    squad_player(1, "Joan Garcia", "POR"),
    squad_player(2, "Kounde", "DEF"),
    squad_player(3, "Balde", "DEF"),
    squad_player(4, "Pedri", "MED"),
    squad_player(5, "Raphinha", "DEL"),
    squad_player(6, "Puado", "DEL"),
]


def my_lineup(saved: list[int] | None) -> SimpleNamespace:
    current = None
    if saved is not None:
        current = SimpleNamespace(
            formation="1-4-3-3",
            players=[SimpleNamespace(player_id=i) for i in saved],
        )
    return SimpleNamespace(squad=SQUAD, current_lineup=current)


def draft(*slots: tuple[int, str], formation: str | None = "1-4-3-3") -> LineupDraft:
    return LineupDraft(
        formation=formation,
        players=[LineupDraftSlot(player_id=p, position_slot=s) for p, s in slots],
    )


def test_a_draft_of_my_own_players_in_their_positions_passes() -> None:
    validate_draft(draft((1, "POR"), (2, "DEF"), (5, "DEL")), my_lineup(None))


def test_a_player_not_in_my_squad_is_refused() -> None:
    with pytest.raises(BusinessRuleError, match="plantilla"):
        validate_draft(draft((1, "POR"), (99, "DEF")), my_lineup(None))


def test_a_player_out_of_his_position_is_refused() -> None:
    with pytest.raises(BusinessRuleError, match="posicion"):
        validate_draft(draft((5, "DEF")), my_lineup(None))


def test_a_repeated_player_is_refused() -> None:
    with pytest.raises(BusinessRuleError, match="repetir"):
        validate_draft(draft((2, "DEF"), (2, "DEF")), my_lineup(None))


def test_the_text_names_the_draft_by_position_and_what_changed() -> None:
    text = draft_text(draft((1, "POR"), (2, "DEF"), (6, "DEL")), my_lineup([1, 2, 5]))
    assert "ONCE EN EDICION (sin enviar)" in text
    assert "1-4-3-3" in text
    assert "POR: Joan Garcia" in text
    assert "DEF: Kounde" in text
    assert "DEL: Puado" in text
    assert "3 de 11" in text
    assert "entra Puado" in text
    assert "sale Raphinha" in text


def test_the_text_says_when_the_draft_equals_the_saved_eleven() -> None:
    text = draft_text(draft((1, "POR"), (2, "DEF")), my_lineup([2, 1]))
    assert "igual que el once guardado" in text


def test_the_text_says_when_nothing_is_saved_yet() -> None:
    text = draft_text(draft((1, "POR"), formation=None), my_lineup(None))
    assert "sin formacion" in text
    assert "no hay once guardado" in text


class CapturingProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self) -> None:
        self.messages: list[Any] = []

    async def run(self, *, system: str, messages: Any, tools: Any, on_progress: Any = None):
        self.messages = list(messages)
        return AssistantReply(text="ok")


async def test_the_question_reaches_the_model_with_the_draft_in_front(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.features.lineup_assistant.context import LineupContext

    async def squad(self: LineupContext) -> SimpleNamespace:
        return my_lineup([1, 2, 5])

    monkeypatch.setattr(LineupContext, "squad", squad)
    provider = CapturingProvider()
    await LineupAssistantService(session=None).ask(  # type: ignore[arg-type]
        season_id=7,
        matchday=6,
        question="¿Revisas este once?",
        user_id=11,
        draft=draft((1, "POR"), (6, "DEL")),
        provider=provider,
    )
    last = provider.messages[-1]
    assert last.role == "user"
    assert last.content.startswith("ONCE EN EDICION")
    assert last.content.rstrip().endswith("¿Revisas este once?")
    assert "entra Puado" in last.content


async def test_without_a_draft_the_question_goes_as_it_is() -> None:
    provider = CapturingProvider()
    await LineupAssistantService(session=None).ask(  # type: ignore[arg-type]
        season_id=7, matchday=6, question="¿Juega Pedri?", user_id=11, provider=provider
    )
    assert provider.messages[-1].content == "¿Juega Pedri?"


async def test_a_bad_draft_never_reaches_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.features.lineup_assistant.context import LineupContext

    async def squad(self: LineupContext) -> SimpleNamespace:
        return my_lineup(None)

    monkeypatch.setattr(LineupContext, "squad", squad)
    provider = CapturingProvider()
    with pytest.raises(BusinessRuleError):
        await LineupAssistantService(session=None).ask(  # type: ignore[arg-type]
            season_id=7,
            matchday=6,
            question="x",
            user_id=11,
            draft=draft((99, "POR")),
            provider=provider,
        )
    assert provider.messages == []
