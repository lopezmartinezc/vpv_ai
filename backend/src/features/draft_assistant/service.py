"""Orchestration for the draft assistant: prompt, provider choice, one turn."""

from __future__ import annotations

import logging
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
)
from src.features.draft_assistant.providers.openai_provider import OpenAIProvider

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

REGLAS DE LA LIGA:
- 26 jugadores por plantilla. Alineacion: 1 portero + 10 de campo.
- Draft serpiente en pretemporada, lineal en el de invierno.
- Reparto objetivo habitual: 2 POR, 8 DEF, 7 MED, 6 DEL.

ESTILO:
Responde en espanol, breve y con numeros concretos del tablero. Cita el nombre
del jugador y la metrica que sostiene lo que dices. Si la respuesta depende del
momento del draft, consulta primero el estado. No inventes datos.
"""


def build_provider() -> AssistantProvider:
    """Pick the configured backend. Raises if it is not usable, so the error
    surfaces as a clear 400 instead of a confusing failure mid-conversation."""
    provider = (settings.assistant_provider or "").lower()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise BusinessRuleError("Falta ANTHROPIC_API_KEY en el backend")
        import anthropic

        return AnthropicProvider(
            client=anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key),
            model=settings.assistant_anthropic_model,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise BusinessRuleError("Falta OPENAI_API_KEY en el backend")
        import openai

        return OpenAIProvider(
            client=openai.AsyncOpenAI(api_key=settings.openai_api_key),
            model=settings.assistant_openai_model,
        )

    raise BusinessRuleError(
        f"ASSISTANT_PROVIDER no valido: {settings.assistant_provider!r} "
        "(usa 'anthropic' u 'openai')"
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
        history: Sequence[ChatMessage] = (),
        provider: AssistantProvider | None = None,
    ) -> AssistantReply:
        question = question.strip()
        if not question:
            raise BusinessRuleError("La pregunta no puede estar vacia")

        ctx = AssistantContext(
            session=self.session,
            season_id=season_id,
            phase=phase,
            anonymize_participants=settings.assistant_anonymize_participants,
        )
        active = provider or build_provider()
        messages = [
            *list(history)[-MAX_HISTORY_MESSAGES:],
            ChatMessage(role="user", content=question),
        ]

        reply = await active.run(
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=build_tools(ctx),
        )
        logger.info(
            "draft_assistant: provider=%s tools=%s truncated=%s",
            active.name,
            [t.name for t in reply.tool_calls],
            reply.truncated,
        )
        return reply
