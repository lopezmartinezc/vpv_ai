"""Paging rosters must cost less than not paging them, not more.

Measured against a real 11-participant draft with the page size as it shipped:
reading every roster took 29 calls of a 30-call budget and sent ~158,000
characters, against 38,174 for the single unpaged call it replaced. The pages
were not the problem - 1,147 characters of players each - the block repeated
on all 29 of them was: missing_by_participant, 4,167 characters, identical
every time.

Two rules, both about the same thing: a page carries a page's worth of
players, and the per-participant needs travel once.
"""

import json

import pytest

from ..schemas import ViewContext
from ..snapshot import RosterPlayer, Snapshot
from ..tools import Rosters, Toolset
from .factories import snapshot


def _crowded(players_per_participant: int = 26) -> tuple[Snapshot, list[int]]:
    """A snapshot whose participants each own a full squad."""
    data = snapshot()
    ids = [p.participant_id for p in data.draft.participants]
    data.roster = [
        RosterPlayer(
            id=100 * owner + n,
            owner_id=owner,
            is_available=True,
            name=f"Jugador {owner}-{n}",
            team="Equipo",
            position="DEF",
        )
        for owner in ids
        for n in range(players_per_participant)
    ]
    return data, ids


def _page(tools: Toolset, **kwargs: int | None) -> dict:
    return json.loads(tools.rosters(Rosters(**kwargs)))["data"]


def test_a_page_holds_a_useful_number_of_players() -> None:
    """Ten at a time turns one answer into twenty-nine questions."""
    data, _ = _crowded()
    tools = Toolset(data, 11, ViewContext())
    assert len(_page(tools, limit=30)["players"]) == 30


def test_reading_every_roster_fits_well_inside_the_call_budget() -> None:
    from ..config import config

    data, _ = _crowded()
    tools = Toolset(data, 11, ViewContext())
    calls, offset = 0, 0
    while True:
        page = _page(tools, offset=offset, limit=30)
        calls += 1
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert calls <= config.max_tool_calls // 3


def test_the_needs_block_travels_once_not_on_every_page() -> None:
    data, _ = _crowded()
    tools = Toolset(data, 11, ViewContext())
    first = _page(tools, offset=0, limit=30)
    later = _page(tools, offset=30, limit=30)
    assert first["missing_by_participant"], "the first page still carries it"
    assert "missing_by_participant" not in later


def test_paging_costs_less_than_the_unpaged_call_it_replaced() -> None:
    data, _ = _crowded()
    tools = Toolset(data, 11, ViewContext())
    total, offset = 0, 0
    while True:
        raw = tools.rosters(Rosters(offset=offset, limit=30))
        total += len(raw)
        page = json.loads(raw)["data"]
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    single = sum(
        len(tools.rosters(Rosters(participant_id=pid, limit=30)))
        for pid in {p.participant_id for p in data.draft.participants}
    )
    assert total < single * 2, "paging must not multiply what one filtered read costs"


def test_a_filtered_roster_still_arrives_in_one_page() -> None:
    data, ids = _crowded()
    tools = Toolset(data, 11, ViewContext())
    page = _page(tools, participant_id=ids[0], limit=30)
    assert page["next_offset"] is None
    assert len(page["players"]) == 26
    assert set(page["missing_by_participant"]) == {str(ids[0])}


@pytest.mark.parametrize("raw", ['{"limit":31}', '{"offset":-1}', '{"participant_id":999999}'])
def test_out_of_range_arguments_are_still_rejected(raw: str) -> None:
    assert Toolset(snapshot(), 11, ViewContext()).dispatch("plantillas", raw).error
