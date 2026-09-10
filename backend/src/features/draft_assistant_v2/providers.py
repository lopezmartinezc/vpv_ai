"""Bounded provider adapters using HTTP, independently of legacy SDK loops."""

from __future__ import annotations

import json
from collections.abc import Sequence

import httpx
from pydantic import BaseModel, Field, JsonValue, TypeAdapter

from src.core.config import settings

from .config import config
from .errors import AssistantError
from .schemas import Capabilities, ProviderName, ProviderOption
from .tools import tool_definitions

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class Call(BaseModel):
    id: str
    name: str
    arguments: str


class Turn(BaseModel):
    calls: list[Call] = Field(default_factory=list)
    output: list[dict[str, JsonValue]] = Field(default_factory=list)
    input_tokens: int = 0
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
        input_tokens=tokens(data, "input_tokens"),
        output_tokens=tokens(data, "output_tokens"),
        incomplete=data.get("status") == "incomplete" or data.get("stop_reason") == "max_tokens",
    )


class Gateway:
    def __init__(self, client: httpx.AsyncClient, provider: ProviderName, model: str) -> None:
        self.client = client
        self.provider = provider
        self.model = model

    def payload(
        self, system: str, messages: Sequence[dict[str, JsonValue]]
    ) -> dict[str, JsonValue]:
        definitions: JsonValue = json.loads(tool_definitions(self.provider))
        common: dict[str, JsonValue] = {"model": self.model, "tools": definitions}
        if self.provider == "openai":
            return {
                **common,
                "instructions": system,
                "input": list(messages),
                "store": False,
                "include": ["reasoning.encrypted_content"],
                "tool_choice": "required",
                "max_output_tokens": config.max_output_tokens,
                "parallel_tool_calls": False,
            }
        return {
            **common,
            "system": system,
            "messages": list(messages),
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
