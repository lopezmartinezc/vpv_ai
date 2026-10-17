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
from collections.abc import Sequence

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.shared.assistant.providers.anthropic_provider import AnthropicProvider
from src.shared.assistant.providers.base import (
    AssistantProvider,
    AssistantReply,
    ChatMessage,
    ProgressCallback,
)
from src.shared.assistant.providers.openai_provider import OpenAIProvider
from src.shared.assistant.tools import ToolSpec

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
    """What the vendor says the key can use. Raises on any failure."""
    if provider == "anthropic":
        import anthropic

        claude_page = await anthropic.AsyncAnthropic(api_key=key).models.list(limit=100)
        return [m.id for m in claude_page.data]
    import openai

    gpt_page = await openai.AsyncOpenAI(api_key=key).models.list()
    return sorted({m.id for m in gpt_page.data if _usable_openai_model(m.id)})


async def _catalogue(provider: str) -> tuple[list[str], list[str]]:
    """(what the vendor listed, what the dropdown offers), cached.

    Never raises: if the vendor call fails (no network, revoked key, changed
    endpoint) the dropdown falls back to the configured default, which is the
    one thing known to work. A broken model list must not break the chat.
    """
    default = default_model_for(provider)
    key = _key_for(provider)
    if not key:
        return [], []

    now = time.monotonic()
    cached = _MODELS_CACHE.get(provider)
    if cached is not None and now - cached[0] < MODELS_TTL_SECONDS:
        return cached[1], cached[2]

    listed: list[str] = []
    try:
        listed = await _vendor_model_ids(provider, key)
    except Exception:
        logger.warning("assistant: could not list %s models", provider, exc_info=True)

    if not listed:
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
    _MODELS_CACHE[provider] = (now, listed, offered)
    return listed, offered


async def list_models(provider: str) -> list[str]:
    """Model ids the chat can offer for ``provider``, configured default first."""
    _, offered = await _catalogue(provider)
    return offered


async def ensure_model_offered(provider: str | None, model: str | None) -> None:
    """Refuse a model the vendor did not list for this key.

    The configured default always passes: it is the operator's choice, and the
    one thing that works when the vendor list cannot be fetched.
    """
    chosen = clean_setting(model)
    if not chosen:
        return
    name = clean_setting(provider or settings.assistant_provider).lower()
    if chosen == default_model_for(name):
        return
    listed, _ = await _catalogue(name)
    if chosen not in listed:
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
        max_output_tokens=settings.assistant_max_output_tokens,
    )


# Questions in flight across both chats. Created lazily so a settings change
# in tests (or a different event loop) is honoured.
_budget: asyncio.Semaphore | None = None
_budget_size = 0


def _reset_budget() -> None:
    global _budget, _budget_size
    _budget, _budget_size = None, 0


def _slots() -> asyncio.Semaphore:
    global _budget, _budget_size
    size = max(1, settings.assistant_max_concurrent)
    if _budget is None or _budget_size != size:
        _budget, _budget_size = asyncio.Semaphore(size), size
    return _budget


async def answer(
    provider: AssistantProvider,
    *,
    system: str,
    messages: Sequence[ChatMessage],
    tools: Sequence[ToolSpec],
    on_progress: ProgressCallback | None = None,
) -> AssistantReply:
    """One turn under the budget: at most ASSISTANT_MAX_CONCURRENT at once,
    and the whole turn (every round included) within ASSISTANT_TIMEOUT_SECONDS.

    A question over the limit is refused at once rather than queued: in a chat
    a clear "busy, try again" beats an answer that arrives a minute late.
    """
    slots = _slots()
    if slots.locked():
        raise BusinessRuleError(
            "El asistente esta ocupado con otras preguntas. Prueba en unos segundos."
        )
    started = time.monotonic()
    async with slots:
        try:
            reply = await asyncio.wait_for(
                provider.run(
                    system=system, messages=messages, tools=tools, on_progress=on_progress
                ),
                timeout=settings.assistant_timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "assistant: %s/%s gave up after %.0fs",
                provider.name,
                getattr(provider, "model", ""),
                settings.assistant_timeout_seconds,
            )
            raise BusinessRuleError(
                f"El asistente ha tardado mas de {settings.assistant_timeout_seconds:.0f} s "
                "y se ha cortado. Prueba una pregunta mas concreta."
            ) from None
    logger.info(
        "assistant: %s/%s answered in %.1fs after %d tool calls%s",
        provider.name,
        getattr(provider, "model", ""),
        time.monotonic() - started,
        len(reply.tool_calls),
        " (truncated)" if reply.truncated else "",
    )
    return reply


def sse_line(event: str, data: dict[str, object]) -> str:
    """One Server-Sent Event. ``json.dumps`` escapes newlines, so a multi-line
    reply cannot terminate the frame early."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
