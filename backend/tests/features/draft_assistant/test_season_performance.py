"""This season's raw output, available to the assistant.

The board blends history with the current season into a projection. Pre-draft
that current season is three matchdays, and the admin reads them directly —
"Eyong and Pépé were scoring before the draft". The assistant could not see
them at all, so it could neither use that signal nor warn about how thin it is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

import pytest

from src.features.draft_assistant import board_tools
from src.features.draft_assistant.board_tools import AssistantContext, build_tools
from src.features.draft_assistant.tools import run_tool


@dataclass
class _Row:
    """Shape of stats.PlayerStatRow, only the fields the tools read."""

    player_id: int
    display_name: str
    position: str
    team_name: str
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    minutes_played: int = 0
    matchdays_played: int = 0
    started_count: int = 0
    avg_points: float = 0.0
    total_points: int = 0
    avg_marca: float | None = None
    avg_as: float | None = None


@dataclass
class _Adv:
    player_id: int
    pp90: float = 0.0
    p10: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    cv: float = 0.0
    form_5: float | None = None
    trend: str = "stable"


@dataclass
class _Draft:
    phase: str = "preseason"
    draft_type: str = "snake"
    status: str = "active"
    participants: list[Any] = field(default_factory=list)
    picks: list[Any] = field(default_factory=list)
    next_participant_id: int | None = None


@dataclass
class _Player:
    player_id: int
    display_name: str
    position: str
    team_name: str
    priority: float | None = 100.0
    priority_base: float | None = 100.0
    vorp: float | None = 5.0
    next_gap: float | None = None
    position_tier: str | None = "solid"
    position_rank: int | None = 1
    participation: float | None = 0.9
    overall_rank: int | None = 1
    exp_games_remaining: float | None = 30.0
    proj_rest_points: float | None = 200.0
    event_share: float | None = 0.6
    team_goals_conceded: float | None = 1.0
    games_played: int = 30
    seasons_played: int = 2
    avg_points: float = 6.0
    goals: int = 5
    assists: int = 2
    marca_avg: float | None = 2.0
    as_avg: float | None = 2.0
    consistency: float = 0.5
    manual_value: float | None = None
    note: str | None = None
    tags: list[str] = field(default_factory=list)
    is_peak_year: bool = False
    is_bench_risk: bool = False
    is_penalty_taker: bool = False
    is_new: bool = False
    team_changed: bool = False
    # Which season the raw figures above describe, and the one before it.
    ref_season_name: str | None = "2026-2027"
    previous_season: object | None = None


EYONG = _Player(7, "Etta Eyong", "DEL", "Levante")


def _ctx(rows: list[_Row], adv: list[_Adv]) -> AssistantContext:
    ctx = AssistantContext(
        session=None,  # type: ignore[arg-type]
        season_id=1,
        phase="preseason",
    )

    class _Board:
        players: ClassVar[list[Any]] = [EYONG]
        participant_count = 11

    async def board() -> Any:
        return _Board()

    async def draft() -> Any:
        return _Draft()

    async def perf() -> Any:
        return {
            r.player_id: (r, next((a for a in adv if a.player_id == r.player_id), None))
            for r in rows
        }

    ctx.board = board  # type: ignore[method-assign]
    ctx.draft = draft  # type: ignore[method-assign]
    ctx.season_perf = perf  # type: ignore[method-assign]
    return ctx


@pytest.fixture(autouse=True)
def _clear() -> None:
    board_tools._BOARD_CACHE.clear()


@pytest.mark.asyncio
async def test_this_season_shows_up_in_the_player_detail() -> None:
    rows = [
        _Row(
            7,
            "Etta Eyong",
            "DEL",
            "Levante",
            goals=4,
            matchdays_played=3,
            started_count=3,
            total_points=60,
            avg_points=20.0,
        )
    ]
    tools = build_tools(_ctx(rows, [_Adv(7, pp90=7.5, form_5=None, trend="rising")]))

    out = await run_tool(tools, "detalle_jugador", {"nombre": "Eyong"})

    assert "Esta temporada" in out
    assert "4" in out  # goals
    assert "3" in out  # matchdays played


@pytest.mark.asyncio
async def test_the_detail_says_when_there_is_nothing_yet() -> None:
    """A player with no minutes must read as "no data", not as zeros that look
    like a bad start."""
    tools = build_tools(_ctx([], []))

    out = await run_tool(tools, "detalle_jugador", {"nombre": "Eyong"})

    assert "sin datos" in out.lower()


@pytest.mark.asyncio
async def test_rendimiento_lists_this_season_ranked() -> None:
    rows = [
        _Row(7, "Etta Eyong", "DEL", "Levante", goals=4, matchdays_played=3, total_points=60),
        _Row(8, "Otro", "DEL", "Getafe", goals=0, matchdays_played=3, total_points=12),
    ]
    tools = build_tools(_ctx(rows, []))

    out = await run_tool(tools, "rendimiento_temporada", {"orden": "puntos"})

    assert out.index("Etta Eyong") < out.index("Otro")


@pytest.mark.asyncio
async def test_rendimiento_warns_how_thin_the_sample_is() -> None:
    """Three matchdays of goals is what made Eyong and Pépé look like stars.
    The tool has to carry that caveat or it invites the same mistake."""
    rows = [_Row(7, "Etta Eyong", "DEL", "Levante", goals=4, matchdays_played=3)]
    tools = build_tools(_ctx(rows, []))

    out = await run_tool(tools, "rendimiento_temporada", {})

    assert "jornada" in out.lower()
    assert "no es una proyeccion" in out.lower() or "no proyecta" in out.lower()


@pytest.mark.asyncio
async def test_rendimiento_filters_by_position() -> None:
    rows = [
        _Row(7, "Delantero", "DEL", "Levante", total_points=60, matchdays_played=3),
        _Row(9, "Medio", "MED", "Getafe", total_points=90, matchdays_played=3),
    ]
    tools = build_tools(_ctx(rows, []))

    out = await run_tool(tools, "rendimiento_temporada", {"posicion": "DEL"})

    assert "Delantero" in out
    assert "Medio" not in out
