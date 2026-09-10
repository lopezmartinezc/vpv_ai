"""When a tool call is rejected, tell the model what was wrong with it.

One generic "revisa tipos, campos, límites e IDs" covered every failure: a
limit out of range, an unknown field, an explanation over the length cap, an
evidence id the model never actually consulted. Those need different
corrections, and a model that cannot tell which one it hit retries blind and
spends the round budget on guesses.
"""

import json

from ..schemas import ViewContext
from ..tools import Final, Toolset
from .factories import snapshot


def _tools() -> Toolset:
    return Toolset(snapshot(), 11, ViewContext())


def test_an_uncited_evidence_id_is_named_as_the_problem() -> None:
    tools = _tools()
    raw = json.dumps(
        {"explanation": "Mira la tarjeta.", "player_ids": [1], "evidence_ids": ["player:1"]}
    )
    result = tools.dispatch("responder", raw)
    assert result.error
    assert "consultad" in result.content.lower() or "citar" in result.content.lower()


def test_a_field_out_of_range_is_named_with_its_field() -> None:
    result = _tools().dispatch("buscar_jugadores", '{"limit":5000}')
    assert result.error
    assert "limit" in result.content


def test_an_unknown_field_is_named() -> None:
    result = _tools().dispatch("buscar_jugadores", '{"season_id":3}')
    assert result.error
    assert "season_id" in result.content


def test_an_unknown_tool_says_so() -> None:
    result = _tools().dispatch("ejecutar_sql", "{}")
    assert result.error
    assert "desconocida" in result.content.lower()


def test_error_content_stays_bounded() -> None:
    """A validation error over a huge payload must not echo the payload back."""
    result = _tools().dispatch("buscar_jugadores", json.dumps({"team": "x" * 50000}))
    assert result.error
    assert len(result.content) < 2000


def test_a_detailed_explanation_has_room() -> None:
    """Four thousand characters is about a thousand tokens — too tight for a
    comparison of three players in detailed mode, and a rejection here costs a
    whole round plus the output tokens already spent writing it."""
    tools = _tools()
    tools.detail(1)
    long = Final(explanation="x" * 6000, player_ids=[1], evidence_ids=["player:1"])
    assert tools.finish(long).final is not None
