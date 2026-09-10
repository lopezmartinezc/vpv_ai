import json

import httpx
import pytest
from pydantic import JsonValue

from ..config import config
from ..engine import conversation, execute_calls, run_engine
from ..providers import Call, Gateway, Turn, parse_turn
from ..schemas import Exchange, History, ProviderName, Usage, ViewContext
from ..service import build_answer, revalidate
from ..tools import Toolset
from .factories import pick, request, snapshot


async def progress(name: str) -> None:
    assert name


def test_provider_payload_privacy_and_caps() -> None:
    gateway = Gateway(httpx.AsyncClient(), "openai", "test-model")
    payload = gateway.payload("rules", [{"role": "user", "content": "question"}])
    assert payload["store"] is False
    assert payload["include"] == ["reasoning.encrypted_content"]
    assert payload["max_output_tokens"] == config.max_output_tokens
    assert payload["tool_choice"] == "required"
    assert "previous_response_id" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_provider_round_trip(provider: str) -> None:
    name: ProviderName = "openai" if provider == "openai" else "anthropic"
    args: dict[str, JsonValue] = {
        "explanation": "Compara los datos de la tarjeta.",
        "player_ids": [1],
        "evidence_ids": ["player:1"],
    }

    def handler(req: httpx.Request) -> httpx.Response:
        if name == "openai":
            body: dict[str, JsonValue] = {
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "c1",
                        "name": "responder",
                        "arguments": json.dumps(args),
                    }
                ]
            }
        else:
            body = {
                "content": [{"type": "tool_use", "id": "c1", "name": "responder", "input": args}]
            }
        return httpx.Response(
            200, json={**body, "usage": {"input_tokens": 12, "output_tokens": 7}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        usage = Usage()
        result = await run_engine(
            Gateway(client, name, "test"),
            Toolset(snapshot(), 11, ViewContext()),
            request(),
            History(),
            progress,
            usage,
        )
    assert result is not None and result.player_ids == [1]
    assert usage.input_tokens == 12 and usage.output_tokens == 7


@pytest.mark.asyncio
async def test_ungrounded_plain_text_never_becomes_a_recommendation() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"output": [{"type": "message", "content": "Invented player"}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await run_engine(
            Gateway(client, "openai", "test"),
            Toolset(snapshot(), 11, ViewContext()),
            request(),
            History(),
            progress,
            Usage(),
        )
    assert result is None


def test_incomplete_and_invalid_wire_arguments() -> None:
    turn = parse_turn(
        "openai",
        {
            "status": "incomplete",
            "output": [
                {"type": "function_call", "name": "test", "call_id": "a", "arguments": "[]"}
            ],
        },
    )
    assert turn.incomplete and turn.calls[0].arguments == "[]"
    assert parse_turn("anthropic", {"stop_reason": "max_tokens"}).incomplete


def test_results_echo_provider_call_ids() -> None:
    call = Call(id="id1", name="estado_draft", arguments="{}")
    for name in ("openai", "anthropic"):
        gateway = Gateway(httpx.AsyncClient(), "openai" if name == "openai" else "anthropic", "m")
        messages: list[dict[str, JsonValue]] = []
        gateway.append_results(
            messages,
            Turn(output=[{"type": "reasoning", "encrypted_content": "x"}]),
            [(call, "ok")],
        )
        assert "id1" in json.dumps(messages)
        assert "encrypted_content" in json.dumps(messages)


@pytest.mark.asyncio
async def test_repeated_calls_and_total_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "max_tool_calls", 2)
    calls = [Call(id=str(i), name="estado_draft", arguments="{}") for i in range(5)]
    usage = Usage()
    final, outputs = await execute_calls(
        Turn(calls=calls), Toolset(snapshot(), 11, ViewContext()), progress, usage, set()
    )
    assert final is None and usage.tool_calls == 2
    assert "repetida" in outputs[-1][1]


def test_history_keeps_complete_exchanges_with_long_answers() -> None:
    data = snapshot()
    answer = build_answer(data, Toolset(data, 11, ViewContext()), None, request(), Usage())
    answer.text = "x" * 9000
    history = History(exchanges=[Exchange(question="antes", answer=answer)] * 10)
    messages = conversation(history, "ahora")
    assert len(messages) % 2 == 1
    assert messages[-1]["content"] == "ahora"
    assert len(json.dumps(messages)) < 18000


def test_revalidation_removes_cards_when_taken_or_board_edited() -> None:
    data = snapshot()
    tools = Toolset(data, 11, ViewContext())
    answer = build_answer(data, tools, None, request(), Usage())
    assert revalidate(answer, data).status == "incomplete"
    data.draft.picks = [pick()]
    assert revalidate(answer, data).status == "stale"
    assert answer.cards == []


def test_nonparticipant_fallback_is_explicit() -> None:
    data = snapshot()
    answer = build_answer(data, Toolset(data, 999, ViewContext()), None, request(), Usage())
    assert "No participas" in answer.warnings[0]
    assert answer.cards[0].player_id == 4
