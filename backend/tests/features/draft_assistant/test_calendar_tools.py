"""Calendar access for the assistant.

The question that prompted this: "si tengo a Soria, dame los partidos de los
demas cuando el Getafe se enfrente a los equipos top". Answering it needs two
things the assistant did not have — the fixture list, and the opponent's
strength graded for the position being asked about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.features.draft_assistant.board_tools import AssistantContext, build_tools
from src.features.draft_assistant.tools import run_tool
from src.features.stats.fixtures import Fixture


def fx(md: int, team: str, rival: str, atk: float, dfc: float, home: bool = True) -> Fixture:
    return Fixture(
        matchday=md,
        team_id=hash(team) % 1000,
        team_name=team,
        opponent_id=hash(rival) % 1000,
        opponent_name=rival,
        home=home,
        opponent_attack=atk,
        opponent_defence=dfc,
    )


#: Getafe faces Real Madrid (prolific) on J11 and Elche (toothless) on J12.
FIXTURES = [
    fx(11, "Getafe", "Real Madrid", 2.10, 0.95),
    fx(11, "Real Madrid", "Getafe", 1.05, 1.20),
    fx(11, "Alavés", "Elche", 0.85, 1.80),
    fx(11, "Elche", "Alavés", 1.00, 1.15),
    fx(12, "Getafe", "Elche", 0.85, 1.80),
    fx(12, "Elche", "Getafe", 1.05, 1.20),
    fx(12, "Alavés", "Barcelona", 2.20, 0.90),
    fx(12, "Barcelona", "Alavés", 1.00, 1.15),
]


@dataclass
class _Draft:
    phase: str = "preseason"
    draft_type: str = "snake"
    status: str = "active"
    participants: list[Any] = field(default_factory=list)
    picks: list[Any] = field(default_factory=list)
    next_participant_id: int | None = None


def _ctx() -> AssistantContext:
    ctx = AssistantContext(session=None, season_id=1, phase="preseason")  # type: ignore[arg-type]

    class _Board:
        players: list[Any] = []
        participant_count = 13

    async def board() -> Any:
        return _Board()

    async def draft() -> Any:
        return _Draft()

    async def fixtures() -> Any:
        return FIXTURES

    async def perf() -> Any:
        return {}

    ctx.board = board  # type: ignore[method-assign]
    ctx.draft = draft  # type: ignore[method-assign]
    ctx.fixtures = fixtures  # type: ignore[method-assign]
    ctx.season_perf = perf  # type: ignore[method-assign]
    return ctx


@pytest.mark.asyncio
async def test_calendario_lists_a_teams_fixtures_with_difficulty() -> None:
    out = await run_tool(build_tools(_ctx()), "calendario", {"equipo": "Getafe"})
    assert "Real Madrid" in out and "Elche" in out
    assert "J11" in out and "J12" in out


@pytest.mark.asyncio
async def test_difficulty_is_reported_for_the_position_asked_about() -> None:
    # Same two fixtures, opposite readings: Real Madrid is hard for a keeper,
    # Elche easy; for a forward Elche's leaky defence is the soft one.
    por = await run_tool(
        build_tools(_ctx()), "calendario", {"equipo": "Getafe", "posicion": "POR"}
    )
    j11 = [line for line in por.splitlines() if "J11" in line][0]
    j12 = [line for line in por.splitlines() if "J12" in line][0]
    assert "dificil" in j11
    assert "facil" in j12


@pytest.mark.asyncio
async def test_alternativas_answers_the_keeper_question() -> None:
    """ "Si tengo a Soria, quien juega facil las jornadas duras del Getafe."""
    out = await run_tool(
        build_tools(_ctx()),
        "alternativas_calendario",
        {"equipo": "Getafe", "posicion": "POR"},
    )
    # J11 is Getafe's hard one; Alavés play toothless Elche that week.
    assert "J11" in out
    assert "Alavés" in out
    # J12 is easy for Getafe, so it is not a matchday needing cover.
    assert "J12" not in out


@pytest.mark.asyncio
async def test_alternativas_says_so_when_nothing_is_hard() -> None:
    out = await run_tool(
        build_tools(_ctx()),
        "alternativas_calendario",
        {"equipo": "Elche", "posicion": "DEL"},
    )
    assert "ninguna" in out.lower() or "no hay" in out.lower()


@pytest.mark.asyncio
async def test_an_unknown_team_says_so_rather_than_returning_nothing() -> None:
    out = await run_tool(build_tools(_ctx()), "calendario", {"equipo": "Cadiz"})
    assert "no encuentro" in out.lower()
