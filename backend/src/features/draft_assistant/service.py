"""Orchestration for the draft assistant: prompt, provider choice, one turn."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.features.draft_assistant.board_tools import AssistantContext, build_tools
from src.features.draft_assistant.providers.anthropic_provider import AnthropicProvider
from src.features.draft_assistant.providers.base import (
    AssistantProvider,
    AssistantReply,
    ChatMessage,
    ProgressCallback,
)
from src.features.draft_assistant.providers.openai_provider import OpenAIProvider
from src.features.stats.participation import ParticipationModel

logger = logging.getLogger(__name__)

# Conversation kept for the whole draft rather than a handful of turns. Not
# unbounded, and not for rationing: every question resends the history, so cost
# grows quadratically with it. 80 messages is ~40 exchanges — more than a draft
# needs — and past that the oldest turns drop off while the chat keeps working.
MAX_HISTORY_MESSAGES = 80

# The single most important line in this feature. The draft order is already
# computed and backtested over 7 seasons (Spearman 0.464); an LLM's own opinion
# on La Liga players is worse than that and its squad knowledge is stale. So the
# assistant is an interface to the data, never a competing ranking.
SYSTEM_PROMPT = """\
Eres el asistente del draft de la Liga VPV Fantasy, una liga fantasy de La Liga
espanola entre amigos. Hablas con el administrador durante el draft en vivo.

REGLA PRINCIPAL, POR ENCIMA DE TODO:
El orden de fichaje YA esta calculado y validado con backtest sobre 7 temporadas
reales. NO lo recalcules, NO propongas un ranking propio y NO opines sobre
jugadores desde tu conocimiento previo: tu informacion sobre plantillas y
mercado esta desactualizada y es peor que el modelo. Responde SIEMPRE
consultando las herramientas. Si una herramienta no da el dato, dilo claramente
en vez de rellenarlo.

TU TRABAJO:
- Explicar: por que un jugador esta por encima de otro, leyendo sus metricas.
- Comparar: entre los disponibles, cual encaja mejor con la plantilla actual.
- Avisar: concentracion de jugadores del mismo equipo, huecos por posicion,
  saltos grandes en una posicion.
- Cronometrar: si conviene coger a alguien YA o se puede esperar al siguiente
  turno. Para esto consulta SIEMPRE proximos_turnos: en draft serpiente la
  espera entre turnos es muy desigual (en el giro se elige dos veces seguidas,
  desde arriba del orden se esperan casi dos rondas), y sin ese dato la
  recomendacion de esperar puede ser justo la contraria de la correcta.

COMO LEER LAS METRICAS:
- Prioridad: puntos proyectados para el resto de temporada, ajustados por riesgo
  y por los tags del admin. ES EL ORDEN MAESTRO. Base es lo mismo sin los tags.
- VORP: valor por plaza sobre el reemplazo de su posicion (participantes x
  plazas de titular). Sirve para comparar ENTRE posiciones.
- Salto: Prioridad que pierdes si dejas pasar a este jugador y esperas al
  siguiente de su posicion. Alto = cogelo ya.
- Disponibilidad (participacion): fraccion de la temporada que se espera que
  juegue, 0 a 1. Baja = bueno cuando juega pero juega poco.
- Tier: elite / solid / normal / weak. Para porteros, team_dependent.
- Fiabilidad (event_share): parte de los puntos que viene de hechos concretos
  (goles, asistencias, porterias a cero) frente a notas de periodico. Alta =
  mas repetible.
- Tags del admin (titular, rotacion, suplente, duda, gol, penaltis, lesion,
  objetivo, evitar): los pone el administrador y mandan sobre la estimacion del
  modelo.

RENDIMIENTO DE ESTA TEMPORADA (rendimiento_temporada):
Son los partidos REALES ya jugados, no una proyeccion. Antes del draft son 3-5
jornadas. Usalo para ver QUIEN ESTA JUGANDO y en que rol -- titularidades,
minutos, si un fichaje ha entrado bien, si alguien ha perdido el puesto -- que
es informacion que la Prioridad tarda en recoger. NO lo uses para ordenar el
draft: la Prioridad ya mezcla estas jornadas con el historico y le da el peso
que merecen. Un arranque caliente en 3 jornadas es la trampa clasica: el año
pasado Eyong y Pepe lideraban antes del draft y acabaron en 143 y 169 puntos.
Si citas estos numeros, di siempre cuantas jornadas llevan.

REGLAS DE LA LIGA:
- 26 jugadores por plantilla. Alineacion: 1 portero + 10 de campo.
- Draft serpiente en pretemporada, lineal en el de invierno.
- Reparto objetivo habitual: 2 POR, 8 DEF, 7 MED, 6 DEL.

LO QUE SE HA MEDIDO EN ESTA LIGA (8 temporadas reales; cita estos datos cuando
toque, estan tambien en escasez_historica):
- El pick de primera ronda rinde ~200 puntos de excedente en delantero y ~118 en
  portero. Un portero top NO es pick de primera ronda; el año pasado los dos
  mejores salieron en los picks 4 y 6, detras de tres delanteros.
- En la primera ronda nadie coge defensas (0 de 11), y luego entran cuatro en la
  segunda. Si sobra un pick temprano, ahi hay valor.
- Con 13 participantes solo hay 13-15 porteros que jueguen toda la liga: uno por
  cabeza y sin margen. Cerrar el portero titular entre la ronda 5 y la 7.
- El segundo portero debe ser el SUPLENTE del titular (mismo equipo). Dos
  titulares de equipos distintos realizan 172 puntos; titular + suplente, 194.
  El ultimo portero draftado vale ~32 puntos: ese hueco es para el suplente.
- Un defensa de Madrid/Barca/Atletico puntua mas cuando juega (6,5 vs 4,9 por
  jornada) pero es MENOS probable que sea fijo (34% vs 48%): rota mas. Disp y
  DefEq ya lo ponderan; lo que el modelo no sabe es la noticia de plantilla,
  y para eso estan los tags del admin.

QUIEN TE HABLA:
Hablas con UNA persona concreta, que puede ser o no participante del draft.
Cuando diga "yo", "mi plantilla", "de que voy corto" o "cuando me toca", se
refiere a SI MISMA, no a quien tenga el turno. Consulta estado_draft para saber
quien es y si le toca; plantilla() sin argumento ya devuelve la suya.

ESTILO:
Responde en espanol, breve y con numeros concretos del tablero. Cita el nombre
del jugador y la metrica que sostiene lo que dices. Si la respuesta depende del
momento del draft, consulta primero el estado. No inventes datos.
"""


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

# Model ids arrive from the client. Not whitelisted against the live list — that
# is cached and would reject a model released an hour ago — but constrained to
# the shape a model id actually has, so nothing else can ride in.
_MODEL_ID = re.compile(r"^[A-Za-z0-9._:@-]{1,100}$")

# Model ids are listed live from each vendor rather than hardcoded, so a new
# release shows up in the dropdown without touching the code. Cached because the
# list changes on the order of months and the chat asks for it on every open.
_MODELS_CACHE: dict[str, tuple[float, list[str]]] = {}
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


async def list_models(provider: str) -> list[str]:
    """Model ids the chat can offer for ``provider``, configured default first.

    Never raises: if the vendor call fails (no network, revoked key, changed
    endpoint) the dropdown falls back to the configured default, which is the
    one thing known to work. A broken model list must not break the chat.
    """
    default = default_model_for(provider)
    key = _key_for(provider)
    if not key:
        return []

    now = time.monotonic()
    cached = _MODELS_CACHE.get(provider)
    if cached is not None and now - cached[0] < MODELS_TTL_SECONDS:
        return cached[1]

    ids: list[str] = []
    try:
        if provider == "anthropic":
            import anthropic

            claude_page = await anthropic.AsyncAnthropic(api_key=key).models.list(limit=100)
            ids = [m.id for m in claude_page.data]
        else:
            import openai

            gpt_page = await openai.AsyncOpenAI(api_key=key).models.list()
            ids = sorted({m.id for m in gpt_page.data if _usable_openai_model(m.id)})
    except Exception:
        logger.warning("draft_assistant: could not list %s models", provider, exc_info=True)

    ordered = ([default] if default else []) + [m for m in ids if m != default]
    if not ordered:
        ordered = ids
    _MODELS_CACHE[provider] = (now, ordered)
    return ordered


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

    if provider == "anthropic":
        import anthropic

        return AnthropicProvider(
            client=anthropic.AsyncAnthropic(api_key=key),
            model=chosen,
            max_iterations=settings.assistant_max_tool_rounds,
        )

    import openai

    return OpenAIProvider(
        client=openai.AsyncOpenAI(api_key=key),
        model=chosen,
        max_iterations=settings.assistant_max_tool_rounds,
    )


class DraftAssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ask(
        self,
        *,
        season_id: int,
        phase: str,
        question: str,
        user_id: int = 0,
        history: Sequence[ChatMessage] = (),
        provider_name: str | None = None,
        model: str | None = None,
        provider: AssistantProvider | None = None,
        participation_model: ParticipationModel = ParticipationModel.MIXTO,
        on_progress: ProgressCallback | None = None,
    ) -> AssistantReply:
        question = question.strip()
        if not question:
            raise BusinessRuleError("La pregunta no puede estar vacia")

        ctx = AssistantContext(
            session=self.session,
            season_id=season_id,
            phase=phase,
            user_id=user_id,
            anonymize_participants=settings.assistant_anonymize_participants,
            participation_model=participation_model,
        )
        active = provider or build_provider(provider_name, model)
        messages = [
            *list(history)[-MAX_HISTORY_MESSAGES:],
            ChatMessage(role="user", content=question),
        ]

        reply = await active.run(
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=build_tools(ctx),
            on_progress=on_progress,
        )
        # Report which backend actually answered, not which one is configured —
        # they differ as soon as the chat's toggle is used.
        reply.provider = active.name
        reply.model = getattr(active, "model", "")
        logger.info(
            "draft_assistant: provider=%s model=%s tools=%s truncated=%s",
            active.name,
            reply.model,
            [t.name for t in reply.tool_calls],
            reply.truncated,
        )
        return reply


def sse_line(event: str, data: dict[str, object]) -> str:
    """One Server-Sent Event. ``json.dumps`` escapes newlines, so a multi-line
    reply cannot terminate the frame early."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
