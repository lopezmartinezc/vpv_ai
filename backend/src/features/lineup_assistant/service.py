"""The lineup chat: its prompt, one turn, and the proposed eleven."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.features.lineup_assistant.context import LineupContext
from src.features.lineup_assistant.optimizer import Valued
from src.features.lineup_assistant.schemas import SuggestedPlayer, SuggestionResponse
from src.features.lineup_assistant.tools import build_tools
from src.shared.assistant.backends import build_provider
from src.shared.assistant.providers.base import (
    AssistantProvider,
    AssistantReply,
    ChatMessage,
    ProgressCallback,
)

logger = logging.getLogger(__name__)

# A lineup chat is a handful of exchanges; the cap only bounds a runaway.
MAX_HISTORY_MESSAGES = 40

# Nothing variable here (no dates, no names): the prompt is cached as a prefix
# and anything that changes between questions would make every one pay in full.
SYSTEM_PROMPT = """\
Eres el asistente de alineacion de la Liga VPV Fantasy, una liga fantasy de La
Liga espanola entre amigos. Hablas con el administrador mientras prepara SU once
de la jornada.

REGLAS DE LA ALINEACION:
- 11 jugadores: 1 portero y 10 de campo, en una formacion valida (reglas).
- Solo puntua quien juega su partido de la jornada.
- La alineacion se guarda en la pantalla, no aqui: tu propones, el decide.
- Hay un cierre antes del primer partido que puntua (calendario_jornada).

DE DONDE SALE CADA DATO (dilo siempre al citarlo):
- Alineaciones probables: FF es futbolfantasy y AF analiticafantasy. Dan el %
  de ser titular esta semana, con la hora de la lectura. Es la mejor senal de
  QUIEN JUEGA: recogen lesiones, rotaciones y noticias. Cita la web y la hora
  ("FF 70 %, lectura del sab 20/09 12:00"). Si las dos discrepan, dilo.
- Titular historico: % de sus ultimos partidos en que fue titular. Mira hacia
  atras: no sabe de la lesion de ayer.
- xPts: puntos esperados por el modelo interno (forma, media, rival, casa o
  fuera). xPts ya lleva descontado el titular historico; "si juega" es sin ese
  descuento. El valor del once propuesto es "si juega" x probabilidad de jugar.
- Estado: duda, lesionado, sancionado, no disponible, rotacion y apercibido
  (a una amarilla de la sancion), con el parte cuando lo hay.

COMO TRABAJAR:
- Consulta SIEMPRE las herramientas antes de responder. No opines de jugadores
  desde tu conocimiento previo: esta desactualizado.
- Para "que once pongo", usa proponer_once y explica los casos justos: quien
  entra por poco, quien depende de una sola web, quien es duda.
- Si falta un dato (sin lectura de las webs, sin prevision), dilo en vez de
  rellenarlo.
- alineaciones_rivales da lo que los demas ya han guardado esta jornada y tu
  rival de playoff si lo hay. Usalo cuando te lo pidan, por ejemplo para
  diferenciarte de tu rival.

ESTILO:
Responde en espanol, breve, con nombres y numeros concretos.
"""


def _suggested(v: Valued) -> SuggestedPlayer:
    c = v.candidate
    return SuggestedPlayer(
        player_id=c.player_id,
        name=c.name,
        position=c.position,
        team_name=c.team_name,
        value=v.value,
        xpts_if_plays=c.xpts_if_plays,
        play_prob=v.play_prob,
        basis=v.basis,
    )


class LineupAssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def context(self, season_id: int, matchday: int, user_id: int) -> LineupContext:
        return LineupContext(
            session=self.session,
            season_id=season_id,
            matchday=matchday,
            user_id=user_id,
            anonymize_participants=settings.assistant_anonymize_participants,
        )

    async def ask(
        self,
        *,
        season_id: int,
        matchday: int,
        question: str,
        user_id: int,
        history: Sequence[ChatMessage] = (),
        provider_name: str | None = None,
        model: str | None = None,
        provider: AssistantProvider | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> AssistantReply:
        question = question.strip()
        if not question:
            raise BusinessRuleError("La pregunta no puede estar vacia")

        ctx = self.context(season_id, matchday, user_id)
        active = provider or build_provider(provider_name, model)
        reply = await active.run(
            system=SYSTEM_PROMPT,
            messages=[
                *list(history)[-MAX_HISTORY_MESSAGES:],
                ChatMessage(role="user", content=question),
            ],
            tools=build_tools(ctx),
            on_progress=on_progress,
        )
        reply.provider = active.name
        reply.model = getattr(active, "model", "")
        logger.info(
            "lineup_assistant: provider=%s model=%s tools=%s truncated=%s",
            active.name,
            reply.model,
            [t.name for t in reply.tool_calls],
            reply.truncated,
        )
        return reply

    async def suggestion(
        self, *, season_id: int, matchday: int, user_id: int, formation: str | None = None
    ) -> SuggestionResponse:
        ctx = self.context(season_id, matchday, user_id)
        if formation and formation not in {f.name for f in await ctx.formations()}:
            raise BusinessRuleError(f"Formacion no valida: {formation}")
        suggestion = await ctx.suggestion(formation)
        if suggestion is None:
            raise BusinessRuleError("Con tu plantilla no se puede formar ninguna formacion valida")
        return SuggestionResponse(
            season_id=season_id,
            matchday_number=matchday,
            formation=suggestion.formation,
            total=suggestion.total,
            eleven=[_suggested(v) for v in suggestion.eleven],
            bench=[_suggested(v) for v in suggestion.bench],
        )
