import json

import pytest
from pydantic import ValidationError

from ..errors import AssistantError
from ..evaluation import formation_needs, rivals_before_turn, sorted_players, turn_context
from ..gain import best_xi, roster_gain
from ..schemas import ViewContext
from ..tools import Toolset, tool_definitions
from .factories import pick, player, snapshot


def test_zero_is_above_negative_and_unknown() -> None:
    data = snapshot()
    view = ViewContext(position="DEL", order="vorp")
    assert [p.player_id for p in sorted_players(data, view)] == [1, 2, 3]
    data.roster[0].owner_id = 2
    assert [p.player_id for p in sorted_players(data, view)] == [2, 3]


def test_gap_ignores_taken_players_and_handles_ties() -> None:
    data = snapshot()
    data.players = [player(1, 100), player(2, 95), player(3, 50)]
    data.roster[1].owner_id = 2
    assert data.card(data.players[0]).available_gap == 50
    data.players[2].priority = 100
    assert data.card(data.players[0]).available_gap == 0


def test_revision_detects_reset_tags_model_and_not_clock() -> None:
    data = snapshot()
    revision = data.revision()
    data.captured_at = "other"
    assert data.revision().draft == revision.draft
    data.draft.picks = [pick()]
    assert data.revision().draft != revision.draft
    prior = data.revision()
    data.draft.picks = [pick(99)]
    assert data.revision().draft != prior.draft
    data.players[0].tags = ["objetivo"]
    assert data.revision().board != revision.board
    data.participation = "historico"
    assert data.revision().board != prior.board


def test_context_is_scoped_and_does_not_use_turn_for_nonparticipant() -> None:
    data = snapshot()
    assert data.target(11, ViewContext()) == 1
    assert data.target(999, ViewContext()) is None
    with pytest.raises(AssistantError):
        Toolset(data, 11, ViewContext(participant_id=88))
    with pytest.raises(AssistantError):
        Toolset(data, 11, ViewContext(selected_player_ids=[88]))


def test_winter_uses_ownership_and_all_formations() -> None:
    data = snapshot()
    data.draft.phase = "winter"
    data.draft.picks = []
    data.roster[3].owner_id = 1
    needs = formation_needs(data, 1)
    assert needs["1-4-3-3"]["POR"] == 0
    assert needs["1-3-5-2"]["DEF"] == 3
    assert formation_needs(data, None) == {}
    output = Toolset(data, 11, ViewContext()).rosters()
    assert "Jugador 4" in output and "Private One" not in output


@pytest.mark.parametrize("status", ["completed", "paused"])
def test_no_future_turn_when_stopped(status: str) -> None:
    data = snapshot()
    data.draft.status = status
    assert turn_context(data, 1)["next_pick"] is None
    assert rivals_before_turn(data, 1) == []


def test_snake_turns_and_end_cap() -> None:
    data = snapshot()
    assert turn_context(data, 1)["following_pick"] == 4
    assert turn_context(data, 1)["picks_between"] == 2
    assert turn_context(data, 2)["picks_between"] == 0
    assert rivals_before_turn(data, 1) == [2]
    data.draft.picks = [pick(number=4)]
    assert turn_context(data, 1)["next_pick"] is None
    data.draft.phase = "winter"
    data.draft.draft_type = "linear"
    assert turn_context(data, 1)["next_pick"] == 5


def test_gain_distinguishes_keeper_cover_from_empty_slot() -> None:
    data = snapshot()
    data.roster[3].owner_id = 1
    reserve = player(5, 80, "POR")
    assert roster_gain(data, 1, reserve) == 0
    assert roster_gain(data, 1, player(6, 80, "DEF")) == 80
    assert roster_gain(data, None, reserve) is None
    assert best_xi([reserve], []) == 80
    assert roster_gain(data, 1, data.players[3]) == 0


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        "null",
        '{"limit":"50"}',
        '{"limit":5000}',
        '{"position":"INVALID"}',
        '{"season_id":3}',
        '{"limit":1.5}',
        '{"limit":true}',
    ],
)
def test_tool_arguments_are_fully_validated(raw: str) -> None:
    result = Toolset(snapshot(), 11, ViewContext()).dispatch("buscar_jugadores", raw)
    assert result.error and result.final is None


def test_final_requires_consulted_ids_and_evidence() -> None:
    tools = Toolset(snapshot(), 11, ViewContext())
    raw = '{"explanation":"Mira la tarjeta.","player_ids":[1],"evidence_ids":["player:1"]}'
    assert tools.dispatch("responder", raw).error
    assert not tools.dispatch("detalle_jugador", '{"player_id":1}').error
    assert tools.dispatch("responder", raw).final is not None
    assert tools.dispatch("ejecutar_sql", "{}").error
    assert tools.dispatch("detalle_jugador", '{"player_id":999}').error


def test_bootstrap_contains_context_and_no_participant_names() -> None:
    tools = Toolset(snapshot(), 11, ViewContext(selected_player_ids=[2], position="DEL"))
    output = tools.state() + tools.evaluate()
    assert "Private One" not in output
    assert '"selected_player_ids": [2]' in output
    assert "player:2" in tools.evidence
    for provider in ("openai", "anthropic"):
        definitions = json.loads(tool_definitions(provider))
        assert len(definitions) == 8


def test_request_rejects_cross_scope_fields() -> None:
    with pytest.raises(ValidationError):
        ViewContext.model_validate({"draft_id": 10})
