"""Provider-neutral tool definitions and dispatch for the draft assistant.

A tool is declared ONCE as a JSON Schema plus an async handler, then adapted to
whatever shape the active provider wants. That is what makes the assistant
swappable between Anthropic and OpenAI without writing the tools twice.

``run_tool`` is the security boundary. Everything the model sends arrives here
as untrusted input, so it:

* passes through only arguments the schema declares — season/draft/participant
  scoping comes from the request and the JWT, never from the model;
* clamps numbers to the schema's ``minimum``/``maximum``;
* turns an unknown tool name or a handler crash into an error string the model
  can read, instead of an exception that kills the request mid-draft.

There is deliberately no "run arbitrary SQL" tool. Player names and tags come
from scraping and manual entry and end up inside the prompt, so free-form SQL
would be an injection surface — and a stray unindexed scan would lock a table
in the middle of a live draft. The model chooses WHAT to ask, never HOW.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class ToolSpec:
    """One tool, declared independently of any provider's wire format."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema (object)
    handler: ToolHandler


def to_anthropic_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    """Messages API shape: the schema lives under ``input_schema``."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }
        for t in tools
    ]


def to_openai_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    """Responses API shape: flat, with the schema under ``parameters``.

    Note this is NOT the nested ``{"function": {...}}`` shape of the older
    chat-completions API.
    """
    return [
        {
            "type": "function",
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        }
        for t in tools
    ]


def _clamp(value: Any, schema: dict[str, Any]) -> Any:
    """Clamp a numeric argument to the schema's bounds.

    The model asking for 5000 rows gets the declared maximum, not a board dump.
    """
    if not isinstance(value, int | float) or isinstance(value, bool):
        return value
    maximum = schema.get("maximum")
    minimum = schema.get("minimum")
    if isinstance(maximum, int | float) and value > maximum:
        value = maximum
    if isinstance(minimum, int | float) and value < minimum:
        value = minimum
    return value


def sanitize_arguments(spec: ToolSpec, raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only declared arguments, clamped to their declared bounds."""
    properties = spec.parameters.get("properties", {})
    clean: dict[str, Any] = {}
    for key, value in raw.items():
        prop = properties.get(key)
        if prop is None:
            logger.warning("draft_assistant: dropped undeclared arg %r for %s", key, spec.name)
            continue
        clean[key] = _clamp(value, prop)
    return clean


async def run_tool(tools: Sequence[ToolSpec], name: str, arguments: dict[str, Any]) -> str:
    """Dispatch one model-requested tool call. Never raises."""
    spec = next((t for t in tools if t.name == name), None)
    if spec is None:
        logger.warning("draft_assistant: unknown tool %r", name)
        return (
            f"Error: la herramienta '{name}' no existe. "
            f"Disponibles: {', '.join(t.name for t in tools)}."
        )

    clean = sanitize_arguments(spec, arguments)
    try:
        return await spec.handler(**clean)
    except Exception:
        logger.exception("draft_assistant: tool %s failed", name)
        return f"Error al ejecutar '{name}'. Prueba otra consulta o dilo en la respuesta."
