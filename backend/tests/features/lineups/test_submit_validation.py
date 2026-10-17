"""The server decides where a player may line up, not the request.

submit_lineup counted the slots it was sent and checked ownership, but never
compared each slot with the player's own position. A request built by hand
could field four forwards by calling three of them defenders — the formation
limit, the whole point of the game, held only on the honour system. Scoring
was unaffected (it reads player_stats.position), the formation was not.

admin_edit_lineup was looser still: no ownership check at all, and no check
that the participant belongs to the season in the URL.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.lineups.schemas import LineupPlayerSlot, LineupSubmitRequest
from src.features.lineups.service import LineupService

SEASON = 7
MATCHDAY = SimpleNamespace(id=70, number=6, season_id=SEASON, deadline_at=None)
PARTICIPANT = SimpleNamespace(id=3, season_id=SEASON, user_id=11)
FORMATION_433 = SimpleNamespace(formation="1-4-3-3", defenders=4, midfielders=3, forwards=3)

# player_id -> real position, as frozen at the draft
SQUAD = {
    1: "POR",
    **{i: "DEF" for i in range(2, 7)},
    **{i: "MED" for i in range(7, 12)},
    **{i: "DEL" for i in range(12, 17)},
}


def eleven(*overrides: tuple[int, str]) -> LineupSubmitRequest:
    """A valid 1-4-3-3 from the squad, with some slots rewritten."""
    slots = {
        1: "POR",
        2: "DEF",
        3: "DEF",
        4: "DEF",
        5: "DEF",
        7: "MED",
        8: "MED",
        9: "MED",
        12: "DEL",
        13: "DEL",
        14: "DEL",
    }
    for player_id, slot in overrides:
        slots.pop(next(k for k, v in slots.items() if v == slot and k != player_id), None)
        slots[player_id] = slot
    return LineupSubmitRequest(
        formation="1-4-3-3",
        players=[LineupPlayerSlot(player_id=p, position_slot=s) for p, s in slots.items()],
    )


class FakeRepo:
    def __init__(self) -> None:
        self.upserted: list[dict] = []

    async def get_participant_for_user(self, season_id, user_id):
        return PARTICIPANT if (season_id, user_id) == (SEASON, PARTICIPANT.user_id) else None

    async def get_participant(self, season_id, participant_id):
        return PARTICIPANT if (season_id, participant_id) == (SEASON, PARTICIPANT.id) else None

    async def get_matchday(self, season_id, number):
        return MATCHDAY

    async def get_season(self, season_id):
        return SimpleNamespace(id=season_id, lineup_deadline_min=30)

    async def get_valid_formation(self, formation):
        return FORMATION_433 if formation == "1-4-3-3" else None

    async def get_squad_positions(self, participant_id):
        return dict(SQUAD) if participant_id == PARTICIPANT.id else {}

    async def get_lineup(self, participant_id, matchday_id):
        return None

    async def upsert_lineup(self, **kwargs):
        self.upserted.append(kwargs)
        return SimpleNamespace(
            id=99, confirmed=True, confirmed_at=None, telegram_sent=False, **kwargs
        )

    async def get_lineup_players_response(self, lineup_id):
        return []


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> LineupService:
    svc = LineupService(session=SimpleNamespace(flush=_noop))
    svc.repo = FakeRepo()
    monkeypatch.setattr(svc, "_notify_telegram", _noop)
    return svc


async def _noop(*args, **kwargs):
    return None


async def test_a_forward_cannot_be_fielded_as_a_defender(service: LineupService) -> None:
    with pytest.raises(BusinessRuleError, match="posicion"):
        await service.submit_lineup(PARTICIPANT.user_id, SEASON, 6, eleven((15, "DEF")))
    assert service.repo.upserted == []


async def test_a_player_in_his_own_position_is_accepted(service: LineupService) -> None:
    await service.submit_lineup(PARTICIPANT.user_id, SEASON, 6, eleven())
    assert len(service.repo.upserted) == 1


async def test_a_player_of_someone_else_is_still_refused(service: LineupService) -> None:
    with pytest.raises(BusinessRuleError, match="plantilla"):
        await service.submit_lineup(PARTICIPANT.user_id, SEASON, 6, eleven((999, "DEF")))


async def test_admin_edit_refuses_a_foreign_player(service: LineupService) -> None:
    with pytest.raises(BusinessRuleError, match="plantilla"):
        await service.admin_edit_lineup(SEASON, 6, PARTICIPANT.id, eleven((999, "DEF")))
    assert service.repo.upserted == []


async def test_admin_edit_refuses_a_wrong_position(service: LineupService) -> None:
    with pytest.raises(BusinessRuleError, match="posicion"):
        await service.admin_edit_lineup(SEASON, 6, PARTICIPANT.id, eleven((15, "DEF")))


async def test_admin_edit_refuses_a_participant_of_another_season(service: LineupService) -> None:
    with pytest.raises(NotFoundError):
        await service.admin_edit_lineup(SEASON, 6, 4242, eleven())
    assert service.repo.upserted == []
