"""Tool surface and the one piece of caching that could silently go wrong."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.features.draft_assistant import board_tools
from src.features.draft_assistant.board_tools import AssistantContext, build_tools
from src.features.draft_assistant.tools import run_tool


@dataclass
class _Player:
    player_id: int
    display_name: str
    position: str
    team_name: str
    priority: float | None = 100.0
    priority_base: float | None = 100.0
    vorp: float | None = 5.0
    next_gap: float | None = 3.0
    position_tier: str | None = "solid"
    participation: float | None = 0.9
    tags: list[str] | None = None
    is_bench_risk: bool = False
    is_peak_year: bool = False
    is_new: bool = False
    is_drafted: bool = False  # the STALE flag the cache would carry

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


@dataclass
class _Pick:
    pick_number: int
    round_number: int
    participant_id: int
    display_name: str
    player_id: int
    player_name: str
    position: str
    team_name: str
    dropped_player_name: str | None = None


@dataclass
class _Participant:
    participant_id: int
    display_name: str
    draft_order: int | None


@dataclass
class _Draft:
    phase: str
    draft_type: str
    status: str
    participants: list[_Participant]
    picks: list[_Pick]
    next_participant_id: int | None


def _ctx(board_players: list[Any], draft: _Draft) -> AssistantContext:
    ctx = AssistantContext(session=None, season_id=1, phase="preseason")  # type: ignore[arg-type]

    class _Board:
        players = board_players
        participant_count = len(draft.participants)

    async def board() -> Any:
        return _Board()

    async def get_draft() -> Any:
        return draft

    ctx.board = board  # type: ignore[method-assign]
    ctx.draft = get_draft  # type: ignore[method-assign]
    return ctx


def _draft_with(picks: list[_Pick]) -> _Draft:
    return _Draft(
        phase="preseason",
        draft_type="snake",
        status="active",
        participants=[
            _Participant(1, "Ana", 1),
            _Participant(2, "Beto", 2),
        ],
        picks=picks,
        next_participant_id=2,
    )


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    board_tools._BOARD_CACHE.clear()


@pytest.mark.asyncio
async def test_availability_comes_from_live_picks_not_the_cached_flag() -> None:
    """The board is cached for a minute; ownership must not be.

    A player taken seconds ago still carries is_drafted=False on the cached
    board. If the tools trusted that flag the assistant would keep recommending
    someone already gone — the worst possible failure mid-draft.
    """
    taken = _Player(player_id=7, display_name="Lewandowski", position="DEL", team_name="Barcelona")
    free = _Player(player_id=8, display_name="Vinicius", position="DEL", team_name="Real Madrid")
    assert taken.is_drafted is False  # stale flag on the cached board

    draft = _draft_with(
        [_Pick(1, 1, 1, "Ana", 7, "Lewandowski", "DEL", "Barcelona")],
    )
    tools = build_tools(_ctx([taken, free], draft))

    out = await run_tool(tools, "buscar_jugadores", {"solo_disponibles": True})

    assert "Vinicius" in out
    assert "Lewandowski" not in out


@pytest.mark.asyncio
async def test_picks_realizados_filters_by_participant() -> None:
    draft = _draft_with(
        [
            _Pick(1, 1, 1, "Ana", 7, "Lewandowski", "DEL", "Barcelona"),
            _Pick(2, 1, 2, "Beto", 8, "Vinicius", "DEL", "Real Madrid"),
        ]
    )
    tools = build_tools(_ctx([], draft))

    out = await run_tool(tools, "picks_realizados", {"participante": "Participante 1"})

    assert "Lewandowski" in out
    assert "Vinicius" not in out


@pytest.mark.asyncio
async def test_picks_realizados_covers_more_than_the_last_ten() -> None:
    """estado_draft only shows 10; this is the tool that sees the whole draft."""
    picks = [_Pick(i, 1, 1, "Ana", 100 + i, f"Jugador{i}", "MED", "Equipo") for i in range(1, 26)]
    tools = build_tools(_ctx([], _draft_with(picks)))

    out = await run_tool(tools, "picks_realizados", {"limite": 40})

    assert "Jugador1" in out and "Jugador25" in out
    assert "25 picks coinciden" in out


@pytest.mark.asyncio
async def test_proximos_turnos_reports_the_wait_to_the_next_turn() -> None:
    """The snake gap is the whole answer to 'can I wait for this player?'."""
    draft = _draft_with([_Pick(1, 1, 1, "Ana", 7, "X", "DEL", "E")])
    tools = build_tools(_ctx([], draft))

    out = await run_tool(tools, "proximos_turnos", {"cuantos": 4})

    # Two participants, snake: after pick #1 comes #2 (Beto), then #3 (Beto
    # again, round 2 reversed), so Beto picks back to back.
    assert "#2" in out and "#3" in out
    assert "picks de espera" in out


@pytest.mark.asyncio
async def test_plantillas_todas_flags_who_is_short() -> None:
    draft = _draft_with([_Pick(1, 1, 1, "Ana", 7, "Portero", "POR", "E")])
    tools = build_tools(_ctx([], draft))

    out = await run_tool(tools, "plantillas_todas", {})

    # Ana has her keeper; Beto has nothing and is short everywhere.
    assert "Participante 1" in out and "Participante 2" in out
    assert "sin cubrir titulares" in out


def test_every_tool_is_uniquely_named_and_documented() -> None:
    tools = build_tools(_ctx([], _draft_with([])))
    names = [t.name for t in tools]

    assert len(names) == len(set(names))
    assert {"picks_realizados", "proximos_turnos", "plantillas_todas"} <= set(names)
    for t in tools:
        # The description is what makes the model reach for it at the right
        # moment, so an empty one is a real defect, not a style nit.
        assert len(t.description) > 40, t.name
        assert t.parameters["type"] == "object"
