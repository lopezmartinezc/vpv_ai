"""Tool dispatch is the security boundary of the draft assistant.

The model chooses WHAT to ask, never HOW. Everything it sends arrives here as
untrusted input: argument names it invented, limits it inflated, identifiers it
should not be able to reach. These tests pin that boundary.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.features.draft_assistant.tools import (
    ToolSpec,
    run_tool,
    to_anthropic_tools,
    to_openai_tools,
)


def _spec(handler: Any) -> ToolSpec:
    return ToolSpec(
        name="buscar_jugadores",
        description="Busca jugadores en el tablero.",
        parameters={
            "type": "object",
            "properties": {
                "posicion": {"type": "string", "enum": ["POR", "DEF", "MED", "DEL"]},
                "limite": {"type": "integer", "maximum": 50, "minimum": 1},
            },
            "required": [],
        },
        handler=handler,
    )


@pytest.mark.asyncio
async def test_undeclared_arguments_are_dropped() -> None:
    """A model-supplied ``season_id`` must never reach the handler.

    Season/draft/participant scoping comes from the request and the JWT. If the
    model could pass them, a hallucination — or a prompt injection riding in a
    scraped player name — would read another season's board.
    """
    seen: dict[str, Any] = {}

    async def handler(**kwargs: Any) -> str:
        seen.update(kwargs)
        return "ok"

    await run_tool(
        [_spec(handler)],
        "buscar_jugadores",
        {"posicion": "DEL", "season_id": 99, "participant_id": 7},
    )

    assert seen == {"posicion": "DEL"}


@pytest.mark.asyncio
async def test_limit_is_capped_to_schema_maximum() -> None:
    """The model asking for 5000 rows must not be able to dump the board."""
    seen: dict[str, Any] = {}

    async def handler(**kwargs: Any) -> str:
        seen.update(kwargs)
        return "ok"

    await run_tool([_spec(handler)], "buscar_jugadores", {"limite": 5000})

    assert seen == {"limite": 50}


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_string_not_raises() -> None:
    """A hallucinated tool name must feed an error back, not kill the request."""

    async def handler(**kwargs: Any) -> str:
        return "ok"

    out = await run_tool([_spec(handler)], "ejecutar_sql", {"q": "DROP TABLE players"})

    assert "ejecutar_sql" in out
    assert "no existe" in out.lower()


@pytest.mark.asyncio
async def test_handler_failure_returns_error_string_not_raises() -> None:
    """A tool that blows up must not take the whole chat down mid-draft."""

    async def handler(**kwargs: Any) -> str:
        raise RuntimeError("boom")

    out = await run_tool([_spec(handler)], "buscar_jugadores", {})

    assert "error" in out.lower()


def test_anthropic_tool_shape() -> None:
    async def handler(**kwargs: Any) -> str:
        return "ok"

    (tool,) = to_anthropic_tools([_spec(handler)])

    assert tool["name"] == "buscar_jugadores"
    assert tool["description"] == "Busca jugadores en el tablero."
    assert tool["input_schema"]["properties"]["posicion"]["enum"] == [
        "POR",
        "DEF",
        "MED",
        "DEL",
    ]


def test_openai_tool_shape() -> None:
    async def handler(**kwargs: Any) -> str:
        return "ok"

    (tool,) = to_openai_tools([_spec(handler)])

    # Responses API: flat shape, not the nested chat-completions one.
    assert tool["type"] == "function"
    assert tool["name"] == "buscar_jugadores"
    assert tool["parameters"]["properties"]["limite"]["maximum"] == 50
