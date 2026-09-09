"""Anthropic backend for the draft assistant.

Uses the stable Messages API with a hand-written tool loop rather than the SDK's
``tool_runner``. Two reasons: the runner is beta, and it wants tools declared
with its own ``@beta_tool`` decorator — which would mean writing every tool
twice, once per provider. The loop is ~30 lines and symmetric with the OpenAI
one, which is the whole point of the abstraction.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from src.features.draft_assistant.providers.base import (
    AssistantReply,
    ChatMessage,
    ToolCallTrace,
)
from src.features.draft_assistant.tools import ToolSpec, run_tool, to_anthropic_tools

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 4000
DEFAULT_MAX_ITERATIONS = 8


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        client: Any,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._client = client
        self.model = model
        self._max_tokens = max_tokens
        self._max_iterations = max_iterations

    async def run(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> AssistantReply:
        # The rules prompt is identical on every question, so mark it cacheable:
        # cache reads bill at ~10% of input. Anything volatile must stay OUT of
        # here — a timestamp in the prefix silently invalidates the cache and
        # every question pays full price.
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        tool_params = to_anthropic_tools(tools)
        wire: list[dict[str, Any]] = [{"role": m.role, "content": m.content} for m in messages]
        trace: list[ToolCallTrace] = []

        for _ in range(self._max_iterations):
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=self._max_tokens,
                system=system_blocks,
                tools=tool_params,
                messages=wire,
            )

            blocks = list(response.content)
            tool_uses = [b for b in blocks if b.type == "tool_use"]
            if not tool_uses:
                text = "\n".join(b.text for b in blocks if b.type == "text").strip()
                return AssistantReply(text=text, tool_calls=trace)

            wire.append({"role": "assistant", "content": blocks})

            results: list[dict[str, Any]] = []
            for block in tool_uses:
                arguments = dict(block.input or {})
                output = await run_tool(tools, block.name, arguments)
                trace.append(ToolCallTrace(name=block.name, arguments=arguments))
                results.append(
                    {
                        # tool_use_id must match the id the model issued or the
                        # API rejects the whole turn.
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    }
                )
            wire.append({"role": "user", "content": results})

        logger.warning("draft_assistant: anthropic hit the %d-iteration cap", self._max_iterations)
        return AssistantReply(
            text=(
                "Me he quedado sin vueltas consultando datos y no he llegado a una "
                "respuesta. Prueba a preguntar algo mas concreto."
            ),
            tool_calls=trace,
            truncated=True,
        )
