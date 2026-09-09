"""OpenAI backend for the draft assistant.

Uses the Responses API (``client.responses.create``), which is the current
primary surface in the 3.x SDK — not the older chat-completions endpoint. The
differences that matter for the loop:

* the system prompt is ``instructions``, not a message;
* tools are flat (``{"type": "function", "name", "parameters"}``), not nested
  under a ``"function"`` key;
* the model's ``function_call`` items must be echoed back into ``input`` before
  the matching ``function_call_output`` items.

The conversation is kept stateless (items echoed explicitly) rather than using
``previous_response_id``, so nothing about a draft is retained server-side.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from src.features.draft_assistant.providers.base import (
    AssistantReply,
    ChatMessage,
    ToolCallTrace,
)
from src.features.draft_assistant.tools import ToolSpec, run_tool, to_openai_tools

logger = logging.getLogger(__name__)

# Overridable per provider; the real default lives in settings so it can be
# raised in production without a deploy.
DEFAULT_MAX_ITERATIONS = 20


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        client: Any,
        model: str,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._client = client
        self.model = model
        self._max_iterations = max_iterations

    async def run(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> AssistantReply:
        tool_params = to_openai_tools(tools)
        items: list[Any] = [{"role": m.role, "content": m.content} for m in messages]
        trace: list[ToolCallTrace] = []

        for _ in range(self._max_iterations):
            response = await self._client.responses.create(
                model=self.model,
                instructions=system,
                tools=tool_params,
                input=items,
            )

            output = list(response.output)
            calls = [o for o in output if getattr(o, "type", None) == "function_call"]
            if not calls:
                return AssistantReply(text=(response.output_text or "").strip(), tool_calls=trace)

            # Echo every output item back before answering any of them; the API
            # needs the assistant's own turn present to match the call_ids.
            for item in output:
                items.append(item.model_dump(exclude_none=True))

            for call in calls:
                try:
                    arguments = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    logger.warning("draft_assistant: bad JSON args for %s", call.name)
                    arguments = {}
                result = await run_tool(tools, call.name, arguments)
                trace.append(ToolCallTrace(name=call.name, arguments=arguments))
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": result,
                    }
                )

        consulted = ", ".join(dict.fromkeys(t.name for t in trace)) or "ninguna"
        logger.warning(
            "draft_assistant: openai hit the %d-round cap after consulting %s",
            self._max_iterations,
            consulted,
        )
        return AssistantReply(
            text=(
                f"Me he quedado sin vueltas ({self._max_iterations}) consultando datos y no "
                f"he llegado a una respuesta. Ya habia consultado: {consulted}. "
                "Prueba a preguntar algo mas concreto, o sube ASSISTANT_MAX_TOOL_ROUNDS."
            ),
            tool_calls=trace,
            truncated=True,
        )
