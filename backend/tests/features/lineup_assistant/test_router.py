"""The lineup chat and the proposed eleven are the admin's, about the admin."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.features.lineup_assistant import service as lineup_service
from src.features.lineup_assistant.context import LineupContext
from src.shared.assistant.providers.base import AssistantReply, ProgressEvent, ToolCallTrace
from src.shared.assistant.tools import run_tool
from tests.features.lineup_assistant.conftest import person, token


class FakeProvider:
    """Consults mi_plantilla, trying to point it at someone else, and answers
    with what it got."""

    name = "fake"
    model = "fake-1"

    async def run(
        self, *, system: str, messages: Any, tools: Any, on_progress: Any = None
    ) -> AssistantReply:
        if on_progress is not None:
            await on_progress(ProgressEvent("tool", "mi_plantilla", {}))
        text = await run_tool(tools, "mi_plantilla", {"season_id": 999, "user_id": 1})
        return AssistantReply(text=text, tool_calls=[ToolCallTrace("mi_plantilla", {})])


@pytest.fixture
def chat(league: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    async def predictions(self: LineupContext) -> dict:
        return league.predictions

    monkeypatch.setattr(LineupContext, "predictions", predictions)
    monkeypatch.setattr(settings, "assistant_enabled", True)
    monkeypatch.setattr(lineup_service, "build_provider", lambda *a, **k: FakeProvider())
    base = f"/api/lineup-assistant/{league.season.id}/6"
    return SimpleNamespace(base=base, admin=token(league.me))


async def test_nobody_but_an_admin_gets_in(
    client: AsyncClient, db_session: AsyncSession, chat: SimpleNamespace
) -> None:
    someone = token(await person(db_session, "Jugador"))
    question = {"question": "¿Juega Pedri?"}
    assert (
        await client.post(f"{chat.base}/ask", json=question, headers=someone)
    ).status_code == 403
    assert (
        await client.post(f"{chat.base}/ask/stream", json=question, headers=someone)
    ).status_code == 403
    assert (await client.get(f"{chat.base}/suggestion", headers=someone)).status_code == 403
    assert (await client.get(f"{chat.base}/suggestion")).status_code in (401, 403)


async def test_the_suggestion_is_the_admins_best_eleven(
    client: AsyncClient, league: SimpleNamespace, chat: SimpleNamespace
) -> None:
    response = await client.get(f"{chat.base}/suggestion", headers=chat.admin)
    assert response.status_code == 200
    body = response.json()
    names = {p["name"] for p in body["eleven"]}
    assert len(body["eleven"]) == 11
    assert "Frenkie de Jong" not in names and "Raphinha" in names
    assert {p["player_id"] for p in body["eleven"]} <= {p.id for p in league.mine.values()}
    raphinha = next(p for p in body["eleven"] if p["name"] == "Raphinha")
    assert (raphinha["value"], raphinha["play_prob"]) == (5.25, 0.75)
    assert body["total"] == round(sum(p["value"] for p in body["eleven"]), 2)


async def test_a_formation_can_be_imposed_but_not_an_invalid_one(
    client: AsyncClient, chat: SimpleNamespace
) -> None:
    ok = await client.get(f"{chat.base}/suggestion?formacion=1-5-3-2", headers=chat.admin)
    assert ok.status_code == 200 and ok.json()["formation"] == "1-5-3-2"
    assert (
        await client.get(f"{chat.base}/suggestion?formacion=1-2-2-6", headers=chat.admin)
    ).status_code == 422
    assert (
        await client.get(f"{chat.base}/suggestion?formacion=todas", headers=chat.admin)
    ).status_code == 422


async def test_the_chat_answers_about_the_asker_whatever_the_model_asks(
    client: AsyncClient, chat: SimpleNamespace
) -> None:
    response = await client.post(
        f"{chat.base}/ask", json={"question": "¿Juega Pedri?"}, headers=chat.admin
    )
    assert response.status_code == 200
    body = response.json()
    assert "Pedri" in body["reply"] and "Dani Cardenas" not in body["reply"]
    assert body["tool_calls"] == [{"name": "mi_plantilla", "arguments": {}}]
    assert (body["provider"], body["model"]) == ("fake", "fake-1")


async def test_the_stream_reports_each_tool_then_the_answer(
    client: AsyncClient, chat: SimpleNamespace
) -> None:
    response = await client.post(
        f"{chat.base}/ask/stream", json={"question": "Propón mi once"}, headers=chat.admin
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    text = response.text
    assert text.index("event: tool") < text.index("event: done")
    assert '"name": "mi_plantilla"' in text and "Pedri" in text


async def test_the_chat_can_be_switched_off_but_not_the_suggestion(
    client: AsyncClient, chat: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "assistant_enabled", False)
    question = {"question": "¿Juega Pedri?"}
    assert (
        await client.post(f"{chat.base}/ask", json=question, headers=chat.admin)
    ).status_code == 422
    assert (
        await client.post(f"{chat.base}/ask/stream", json=question, headers=chat.admin)
    ).status_code == 422
    assert (await client.get(f"{chat.base}/suggestion", headers=chat.admin)).status_code == 200
