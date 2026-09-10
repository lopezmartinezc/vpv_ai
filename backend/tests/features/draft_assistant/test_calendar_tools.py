"""Calendar access for the assistant.

The question that prompted this: "si tengo a Soria, dame los partidos de los
demas cuando el Getafe se enfrente a los equipos top". Answering it needs two
things the assistant did not have — the fixture list, and the opponent's
strength graded for the position being asked about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

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
        players: ClassVar[list[Any]] = []
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
    # The header now states the loaded range ("J11-J12"), so match the fixture
    # lines themselves rather than the first line mentioning a matchday.
    lineas = [line for line in por.splitlines() if line.startswith("J")]
    j11 = next(line for line in lineas if line.startswith("J11 "))
    j12 = next(line for line in lineas if line.startswith("J12 "))
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
    assert "J11 —" in out
    assert "Alavés" in out
    # J12 is easy for Getafe, so it is not listed as a matchday needing cover.
    assert "J12 —" not in out


@pytest.mark.asyncio
async def test_alternativas_says_so_when_nothing_is_hard() -> None:
    out = await run_tool(
        build_tools(_ctx()),
        "alternativas_calendario",
        {"equipo": "Elche", "posicion": "DEL"},
    )
    assert "ninguna" in out.lower() or "no hay" in out.lower()


@pytest.mark.asyncio
async def test_a_team_with_no_loaded_fixtures_blames_the_calendar_not_the_team() -> None:
    """A missing fixture and a non-existent team look identical in the data —
    ``matches`` simply has no row — so the tool must not let the model conclude
    the team does not exist."""
    out = await run_tool(build_tools(_ctx()), "calendario", {"equipo": "Cadiz"})
    assert "calendario cargado" in out.lower()
    assert "update-calendar" in out
    assert "no existe" not in out.lower().replace("no afirmes que el equipo no existe", "")


# ---------------------------------------------------------------------------
# Coverage: the calendar can simply not be loaded yet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calendario_states_which_matchdays_it_actually_has() -> None:
    """Reported from production: the assistant said "aun no tengo esas jornadas"
    without saying which it did have, so nobody could tell a missing fixture
    from a broken tool."""
    out = await run_tool(build_tools(_ctx()), "calendario", {"equipo": "Getafe"})
    assert "J11" in out and "J12" in out
    # The covered range is stated, so a short horizon is visible.
    assert "cargado" in out.lower()


@pytest.mark.asyncio
async def test_a_team_absent_from_the_loaded_range_says_why() -> None:
    ctx = _ctx()

    async def only_getafe() -> Any:
        return [f for f in FIXTURES if f.team_name == "Getafe"]

    ctx.fixtures = only_getafe  # type: ignore[method-assign]
    out = await run_tool(build_tools(ctx), "calendario", {"equipo": "Alavés"})

    assert "calendario" in out.lower()
    assert "update-calendar" in out


def test_the_horizon_covers_the_rest_of_the_season() -> None:
    """The chat reported the calendar "only loaded to J16" — which was this
    constant at 12, not missing data. A full season is 38 matchdays and the
    output is capped separately by ``limite``."""
    from src.features.draft_assistant.board_tools import FIXTURE_HORIZON

    assert FIXTURE_HORIZON >= 38
