"""Bounded provider adapters using HTTP, independently of legacy SDK loops."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

import httpx
from pydantic import BaseModel, Field, JsonValue, TypeAdapter

from src.core.config import settings

from .config import config
from .errors import AssistantError
from .schemas import Capabilities, ProviderName, ProviderOption
from .tools import tool_definitions

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
logger = logging.getLogger(__name__)
EPHEMERAL: dict[str, JsonValue] = {"type": "ephemeral"}


def cache_last_block(message: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Copy of an Anthropic message with its last content block cache-marked.

    Each round's prompt is the previous round's prompt plus one exchange, so
    marking the newest block lets the provider reuse everything before it.
    String content becomes a single text block; block lists get the marker on
    their last block only. The caller's message is left untouched.
    """
    content = message.get("content")
    if isinstance(content, str):
        blocks: list[JsonValue] = [{"type": "text", "text": content, "cache_control": EPHEMERAL}]
        return {**message, "content": blocks}
    if isinstance(content, list) and content and isinstance(content[-1], dict):
        last: dict[str, JsonValue] = {**content[-1], "cache_control": EPHEMERAL}
        return {**message, "content": [*content[:-1], last]}
    return message


class Call(BaseModel):
    id: str
    name: str
    arguments: str


class Turn(BaseModel):
    calls: list[Call] = Field(default_factory=list)
    output: list[dict[str, JsonValue]] = Field(default_factory=list)
    input_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    incomplete: bool = False


def credentials(provider: ProviderName) -> tuple[str, str]:
    if provider == "openai":
        return settings.openai_api_key.strip(), settings.assistant_openai_model.split("#")[
            0
        ].strip()
    return settings.anthropic_api_key.strip(), settings.assistant_anthropic_model.split("#")[
        0
    ].strip()


def capabilities() -> Capabilities:
    options = []
    for name in ("openai", "anthropic"):
        provider: ProviderName = "openai" if name == "openai" else "anthropic"
        key, default = credentials(provider)
        allowed = config.openai_models if provider == "openai" else config.anthropic_models
        models = list(dict.fromkeys([default, *allowed])) if default else allowed
        if key and models:
            options.append(ProviderOption(name=provider, models=models, default_model=models[0]))
    return Capabilities(
        enabled=config.enabled, providers=options, default=settings.assistant_provider
    )


def validate_provider(provider: ProviderName, model: str) -> None:
    if not config.enabled:
        raise AssistantError("V2_DISABLED", "El chat experimental está desactivado.", 503)
    option = next((p for p in capabilities().providers if p.name == provider), None)
    if option is None or model not in option.models:
        raise AssistantError("MODEL_NOT_ALLOWED", "Proveedor o modelo no habilitado para V2.")


def records(value: JsonValue | None) -> list[dict[str, JsonValue]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def tokens(data: dict[str, JsonValue], key: str) -> int:
    usage = data.get("usage")
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def input_total(provider: ProviderName, data: dict[str, JsonValue]) -> int:
    """Everything sent, under one meaning for both providers.

    OpenAI's input_tokens already is the whole prompt. Anthropic's is only the
    uncached part, with cache reads and writes reported alongside — read as a
    total it shows 24 tokens of input against 6,000 cached, which is what
    production displayed before this existed.
    """
    total = tokens(data, "input_tokens")
    if provider == "anthropic":
        total += tokens(data, "cache_creation_input_tokens") + tokens(
            data, "cache_read_input_tokens"
        )
    return total


def detail(data: dict[str, JsonValue], key: str) -> int:
    """An integer under usage.input_tokens_details, OpenAI's home for cache figures."""
    usage = data.get("usage")
    details = usage.get("input_tokens_details") if isinstance(usage, dict) else None
    value = details.get(key) if isinstance(details, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def cached_tokens(provider: ProviderName, data: dict[str, JsonValue]) -> int:
    """Prefix-cache reads, reported under a different key by each provider."""
    if provider == "anthropic":
        return tokens(data, "cache_read_input_tokens")
    return detail(data, "cached_tokens")


def cache_write_tokens(provider: ProviderName, data: dict[str, JsonValue]) -> int:
    """Stored into cache this request. Anthropic bills these at a premium."""
    if provider == "anthropic":
        return tokens(data, "cache_creation_input_tokens")
    return detail(data, "cache_write_tokens")


def parse_turn(provider: ProviderName, data: dict[str, JsonValue]) -> Turn:
    output = records(data.get("output" if provider == "openai" else "content"))
    calls = []
    for item in output:
        if item.get("type") not in ("function_call", "tool_use"):
            continue
        raw = item.get("arguments") if provider == "openai" else json.dumps(item.get("input"))
        call_id = item.get("call_id" if provider == "openai" else "id")
        if isinstance(item.get("name"), str) and isinstance(call_id, str) and isinstance(raw, str):
            calls.append(Call(id=call_id, name=str(item["name"]), arguments=raw))
    return Turn(
        calls=calls,
        output=output,
        input_tokens=input_total(provider, data),
        cached_tokens=cached_tokens(provider, data),
        cache_write_tokens=cache_write_tokens(provider, data),
        output_tokens=tokens(data, "output_tokens"),
        incomplete=data.get("status") == "incomplete" or data.get("stop_reason") == "max_tokens",
    )


class Gateway:
    def __init__(
        self,
        client: httpx.AsyncClient,
        provider: ProviderName,
        model: str,
        effort: str = "",
        cache_key: str = "",
    ) -> None:
        self.client = client
        self.provider = provider
        self.model = model
        # OpenAI reasoning effort; empty leaves it to the provider. Anthropic
        # ignores it: V2 does not enable thinking there, so it is already quick.
        self.effort = effort
        # OpenAI partitions cache reuse by prompt_cache_key on top of a prefix
        # hash, and asks that related requests share one key. One key per draft
        # state keeps every question at that state in the same partition; the
        # first cross-question hit measured in production came with it.
        # Anthropic's cache is explicit and needs nothing here.
        self.cache_key = cache_key

    def payload(
        self, system: str, messages: Sequence[dict[str, JsonValue]]
    ) -> dict[str, JsonValue]:
        definitions: JsonValue = json.loads(tool_definitions(self.provider))
        common: dict[str, JsonValue] = {"model": self.model, "tools": definitions}
        if self.provider == "openai":
            reasoning: dict[str, JsonValue] = (
                {"reasoning": {"effort": self.effort}} if self.effort else {}
            )
            routing: dict[str, JsonValue] = (
                {"prompt_cache_key": self.cache_key} if self.cache_key else {}
            )
            return {
                **common,
                **reasoning,
                **routing,
                "instructions": system,
                "input": list(messages),
                "store": False,
                "include": ["reasoning.encrypted_content"],
                "tool_choice": "required",
                "max_output_tokens": config.max_output_tokens,
                "parallel_tool_calls": False,
            }
        # Prompt caching, as V1 does: system, tools and the bootstrap evidence are
        # identical on every round of a question, and V1 measured roughly a 4x
        # saving on input by marking them. OpenAI caches long prefixes unasked.
        tools = list(definitions) if isinstance(definitions, list) else []
        if tools and isinstance(tools[-1], dict):
            tools[-1] = {**tools[-1], "cache_control": EPHEMERAL}
        history = list(messages)
        if history:
            history[-1] = cache_last_block(history[-1])
        system_blocks: list[JsonValue] = [
            {"type": "text", "text": system, "cache_control": EPHEMERAL}
        ]
        return {
            **common,
            "tools": tools,
            "system": system_blocks,
            "messages": list(history),
            "max_tokens": config.max_output_tokens,
            "tool_choice": {"type": "any"},
        }

    async def request(self, system: str, messages: Sequence[dict[str, JsonValue]]) -> Turn:
        key, _ = credentials(self.provider)
        if self.provider == "openai":
            url, headers = (
                "https://api.openai.com/v1/responses",
                {"Authorization": f"Bearer {key}"},
            )
        else:
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        response = await self.client.post(
            url, headers=headers, json=self.payload(system, messages)
        )
        if response.is_error:
            # The body is the only thing that tells a rejected parameter from a
            # rotated key from an overloaded upstream. Logged, never shown.
            logger.warning(
                "assistant_v2 provider=%s model=%s status=%s body=%s",
                self.provider,
                self.model,
                response.status_code,
                response.text[:500],
            )
            raise AssistantError(
                "PROVIDER_ERROR", "El proveedor no ha podido responder. Reintenta.", 502
            )
        return parse_turn(self.provider, JSON_OBJECT.validate_json(response.content))

    def append_results(
        self, messages: list[dict[str, JsonValue]], turn: Turn, outputs: list[tuple[Call, str]]
    ) -> None:
        if self.provider == "openai":
            messages.extend(turn.output)
            messages.extend(
                {"type": "function_call_output", "call_id": call.id, "output": value}
                for call, value in outputs
            )
        else:
            content: list[JsonValue] = list(turn.output)
            messages.append({"role": "assistant", "content": content})
            results: list[JsonValue] = [
                {"type": "tool_result", "tool_use_id": call.id, "content": value}
                for call, value in outputs
            ]
            messages.append({"role": "user", "content": results})
