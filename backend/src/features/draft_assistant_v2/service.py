from __future__ import annotations

import asyncio
import logging
import time

import httpx

from . import history
from .config import config
from .engine import STOP_MESSAGES, STOP_TIMEOUT, Progress, run_engine
from .errors import AssistantError
from .evaluation import sorted_players
from .gain import roster_gain
from .providers import Gateway, validate_provider
from .repository import load_snapshot
from .schemas import Answer, AskRequest, Exchange, Revision, Usage
from .snapshot import Snapshot
from .tools import Final, Toolset

logger = logging.getLogger(__name__)


def build_answer(
    snapshot: Snapshot, tools: Toolset, final: Final | None, request: AskRequest, usage: Usage
) -> Answer:
    warnings = []
    if tools.target is None:
        warnings.append("No participas en este draft: selecciona una plantilla para personalizar.")
    if final is None:
        warnings.append(
            "Análisis incompleto. Las tarjetas son opciones del tablero, no una elección personalizada."
        )
        detail = STOP_MESSAGES.get(usage.stop_reason or "")
        if detail:
            warnings.append(detail)
    ids = (
        final.player_ids
        if final
        else [p.player_id for p in sorted_players(snapshot, tools.view)[:3]]
    )
    by_id = {p.player_id: p for p in snapshot.players}
    cards = [snapshot.card(by_id[pid]) for pid in dict.fromkeys(ids)]
    for card in cards:
        card.marginal_gain = roster_gain(snapshot, tools.target, by_id[card.player_id])
    return Answer(
        text=final.explanation if final else "No se completó la explicación. Puedes reintentar.",
        cards=cards,
        evidence_ids=final.evidence_ids if final else ["evaluation"],
        status="current" if final else "incomplete",
        warnings=warnings,
        revision=snapshot.revision(),
        provider=request.provider,
        model=request.model,
        usage=usage,
    )


def revalidate(answer: Answer, fresh: Snapshot) -> Answer:
    revision = fresh.revision()
    if revision.draft != answer.revision.draft or revision.board != answer.revision.board:
        answer.status = "stale"
        answer.warnings.append(
            "El draft o las métricas cambiaron durante el análisis. Actualiza antes de elegir."
        )
        answer.cards = []  # Do not mix old reasoning with new metrics or suggest a taken player.
    return answer


async def analyze(draft_id: int, user_id: int, request: AskRequest, progress: Progress) -> Answer:
    await progress("Leyendo estado y tablero")
    snapshot = await load_snapshot(draft_id, request.participation)
    tools = Toolset(snapshot, user_id, request.context)
    previous = await history.read_history(user_id, draft_id)
    usage = Usage()
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=config.provider_timeout_seconds) as client:
        effort = config.quick_effort if request.mode == "quick" else ""
        gateway = Gateway(client, request.provider, request.model, effort)
        try:
            async with asyncio.timeout(max(1, config.timeout_seconds - 20)):
                final = await run_engine(gateway, tools, request, previous, progress, usage)
        except (TimeoutError, httpx.TimeoutException):
            final = None
            usage.stop_reason = STOP_TIMEOUT
    await progress("Comprobando disponibilidad antes de responder")
    answer = build_answer(snapshot, tools, final, request, usage)
    answer = revalidate(answer, await load_snapshot(draft_id, request.participation))
    usage.latency_ms = int((time.monotonic() - started) * 1000)
    return answer


async def ask(draft_id: int, user_id: int, request: AskRequest, progress: Progress) -> Answer:
    if not request.question.strip():
        raise AssistantError("EMPTY_QUESTION", "Escribe una pregunta.")
    validate_provider(request.provider, request.model)
    lease = await history.acquire(user_id, draft_id)
    try:
        async with asyncio.timeout(config.timeout_seconds):
            answer = await analyze(draft_id, user_id, request, progress)
            await history.save(
                user_id, draft_id, lease, Exchange(question=request.question, answer=answer)
            )
        logger.info(
            "assistant_v2 completed provider=%s model=%s status=%s usage=%s",
            request.provider,
            request.model,
            answer.status,
            answer.usage.model_dump(),
        )
        return answer
    finally:
        await history.release(user_id, draft_id, lease)


async def revision(draft_id: int, participation: str) -> Revision:
    async with asyncio.timeout(15):
        return (await load_snapshot(draft_id, participation)).revision()
