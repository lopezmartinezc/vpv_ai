"""Which model answers: provider and model choice, shared by every chat.

The draft chat and the lineup chat offer the same providers, keys and models;
only their prompts and tools differ.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.shared.assistant.execution import _reset_budget as _reset_budget
from src.shared.assistant.execution import answer as answer
from src.shared.assistant.providers.anthropic_provider import AnthropicProvider
from src.shared.assistant.providers.base import AssistantProvider
from src.shared.assistant.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


def clean_setting(raw: str | None) -> str:
    """Strip a trailing ``# comment`` and surrounding whitespace.

    The backend is started by systemd with ``EnvironmentFile=``, and systemd
    only ignores comments on their OWN line — ``KEY=value  # note`` yields the
    comment as part of the value. Tolerating that here turns a baffling
    "provider not valid" into a working deploy.
    """
    return (raw or "").split("#", 1)[0].strip()


#: Offered in this order. OpenAI first because it is the configured default and
#: because the panel falls back to the first available provider when the default
#: has no key — with Anthropic first, a missing OPENAI_API_KEY silently landed
#: everyone on Claude.
PROVIDERS = ("openai", "anthropic")

# Model ids arrive from the client: constrained to the shape a model id has so
# nothing else rides in, and (ensure_model_offered) to the ones the vendor lists.
_MODEL_ID = re.compile(r"^[A-Za-z0-9._:@-]{1,100}$")

# Model ids are listed live from each vendor rather than hardcoded, so a new
# release shows up in the dropdown without touching the code. Cached because the
# list changes on the order of months and the chat asks for it on every open.
# Per provider: (when, what the vendor listed, what the dropdown offers).
_MODELS_CACHE: dict[str, tuple[float, list[str], list[str]]] = {}
MODELS_TTL_SECONDS = 600.0

# OpenAI's /models returns everything on the account — embeddings, audio, image.
# Only chat-capable families belong in the dropdown. Anthropic's list is already
# just Claude models, so it needs no filtering.
_OPENAI_KEEP_PREFIXES = ("gpt", "o1", "o3", "o4", "chatgpt")
_OPENAI_DROP_MARKERS = (
    "embedding",
    "tts",
    "whisper",
    "dall-e",
    "moderation",
    "audio",
    "image",
    "realtime",
    "transcribe",
    "instruct",
)


def _key_for(provider: str) -> str:
    raw = settings.anthropic_api_key if provider == "anthropic" else settings.openai_api_key
    return clean_setting(raw)


def default_model_for(provider: str) -> str:
    raw = (
        settings.assistant_anthropic_model
        if provider == "anthropic"
        else settings.assistant_openai_model
    )
    return clean_setting(raw)


def available_providers() -> list[str]:
    """Providers that actually have a key, in the order the UI should offer them.

    Lets the chat show only what will work — a toggle that produces a 400 is
    worse than no toggle. Never returns keys, only names.
    """
    return [p for p in PROVIDERS if _key_for(p)]


def _usable_openai_model(model_id: str) -> bool:
    lowered = model_id.lower()
    if any(marker in lowered for marker in _OPENAI_DROP_MARKERS):
        return False
    return lowered.startswith(_OPENAI_KEEP_PREFIXES)


async def _vendor_model_ids(provider: str, key: str) -> list[str]:
    """Fetch with a short timeout, no retries, and a closed SDK client."""
    timeout = settings.assistant_request_timeout_seconds
    if provider == "anthropic":
        import anthropic

        async with anthropic.AsyncAnthropic(api_key=key, timeout=timeout, max_retries=0) as client:
            claude_page = await client.models.list(limit=100)
            return [m.id for m in claude_page.data]
    import openai

    async with openai.AsyncOpenAI(api_key=key, timeout=timeout, max_retries=0) as gpt:
        gpt_page = await gpt.models.list()
        return sorted({m.id for m in gpt_page.data if _usable_openai_model(m.id)})


async def _catalogue(provider: str) -> tuple[list[str], list[str]]:
    """(what the vendor listed, what the dropdown offers), cached.

    On failure only, offer the configured default as an unverified fallback.
    A successful empty list authorizes no models.
    """
    default = default_model_for(provider)
    key = _key_for(provider)
    if not key:
        return [], []

    now = time.monotonic()
    cached = _MODELS_CACHE.get(provider)
    if cached is not None and now - cached[0] < MODELS_TTL_SECONDS:
        return cached[1], cached[2]

    listed, offered = await _fetch_catalogue(provider, key, default)
    _MODELS_CACHE[provider] = (now, listed, offered)
    return listed, offered


async def _fetch_catalogue(provider: str, key: str, default: str) -> tuple[list[str], list[str]]:
    listed: list[str] = []
    failed = False
    try:
        listed = await asyncio.wait_for(
            _vendor_model_ids(provider, key), timeout=settings.assistant_request_timeout_seconds
        )
    except Exception:
        failed = True
        logger.warning("assistant: could not list %s models", provider, exc_info=True)

    if failed:
        offered = [default] if default else []
    elif default in listed:
        offered = [default] + [m for m in listed if m != default]
    else:
        # A default the vendor does not list would fail on first use; say so
        # instead of offering it. The .env is wrong, not the vendor.
        logger.warning(
            "assistant: configured %s model %r is not in the vendor's list", provider, default
        )
        offered = list(listed)
    return listed, offered


async def list_models(provider: str) -> list[str]:
    """Model ids the chat can offer for ``provider``, configured default first."""
    _, offered = await _catalogue(provider)
    return offered


async def ensure_model_offered(provider: str | None, model: str | None) -> None:
    """Only a catalogue outage permits an unverified configured default."""
    name = clean_setting(provider or settings.assistant_provider).lower()
    if name not in PROVIDERS:
        raise BusinessRuleError("Proveedor no valido")
    chosen = clean_setting(model) or default_model_for(name)
    _, offered = await _catalogue(name)
    if chosen not in offered:
        raise BusinessRuleError(f"Modelo no disponible para {name}: {chosen!r}")


def build_provider(name: str | None = None, model: str | None = None) -> AssistantProvider:
    """Build the requested backend, or the configured default.

    ``name`` and ``model`` come from the client (the chat's selectors), so the
    provider is validated against the whitelist and the model against a
    conservative id shape rather than trusted. Raises if unusable, so the error
    surfaces as a clear 400 instead of a vendor auth failure mid-conversation.
    """
    provider = clean_setting(name or settings.assistant_provider).lower()

    if provider not in PROVIDERS:
        raise BusinessRuleError(f"Proveedor no valido: {provider!r} (usa {' u '.join(PROVIDERS)})")

    key = _key_for(provider)
    if not key:
        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        raise BusinessRuleError(f"Falta {env_var} en el backend")

    chosen = clean_setting(model) or default_model_for(provider)
    if not chosen:
        raise BusinessRuleError(f"No hay modelo configurado para {provider}")
    if not _MODEL_ID.match(chosen):
        raise BusinessRuleError(f"Modelo no valido: {chosen!r}")

    timeout = settings.assistant_request_timeout_seconds
    if provider == "anthropic":
        import anthropic

        return AnthropicProvider(
            client=anthropic.AsyncAnthropic(api_key=key, timeout=timeout),
            model=chosen,
            max_tokens=settings.assistant_max_output_tokens,
            max_iterations=settings.assistant_max_tool_rounds,
        )

    import openai

    return OpenAIProvider(
        client=openai.AsyncOpenAI(api_key=key, timeout=timeout),
        model=chosen,
        max_iterations=settings.assistant_max_tool_rounds,
        max_output_tokens=settings.assistant_openai_max_output_tokens,
    )


def sse_line(event: str, data: dict[str, object]) -> str:
    """One Server-Sent Event. ``json.dumps`` escapes newlines, so a multi-line
    reply cannot terminate the frame early."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
