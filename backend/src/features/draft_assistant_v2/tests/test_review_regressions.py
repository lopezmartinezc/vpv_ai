import json
import logging

import httpx
import pytest
from pydantic import ValidationError

from ..config import AssistantSettings
from ..errors import AssistantError
from ..providers import Gateway
from ..schemas import ViewContext
from ..snapshot import RosterPlayer
from ..tools import Rosters, Toolset
from .factories import snapshot


@pytest.mark.parametrize("seconds", [171, 190, 240, 300])
def test_timeout_rejects_values_without_browser_margin(seconds: int) -> None:
    with pytest.raises(ValidationError):
        AssistantSettings(timeout_seconds=seconds)


def test_timeout_accepts_upper_boundary() -> None:
    assert AssistantSettings(timeout_seconds=170).timeout_seconds == 170


def test_large_rosters_can_be_retrieved_without_truncation() -> None:
    data = snapshot()
    pid = data.draft.participants[0].participant_id
    data.roster = [
        RosterPlayer(
            id=i,
            owner_id=pid,
            is_available=True,
            name=f"Jugador {i}",
            team="Equipo",
            position="DEF",
        )
        for i in range(1, 287)
    ]
    tools = Toolset(data, 11, ViewContext())
    found: list[int] = []
    offset = 0
    while True:
        result = tools.rosters(Rosters(participant_id=pid, offset=offset))
        assert len(result) < 24000
        page = json.loads(result)["data"]
        found.extend(p["id"] for p in page["players"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert found == list(range(1, 287))


def test_roster_filter_and_invalid_arguments() -> None:
    tools = Toolset(snapshot(), 11, ViewContext())
    assert tools.dispatch("plantillas", '{"participant_id":999999}').error
    assert tools.dispatch("plantillas", '{"offset":-1}').error
    assert tools.dispatch("plantillas", '{"limit":31}').error
    result = tools.dispatch("plantillas", '{"offset":99999}')
    assert not result.error and json.loads(result.content)["data"]["players"] == []


@pytest.mark.asyncio
async def test_provider_errors_never_log_response_body(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="SECRET_API_KEY PRIVATE_USER_QUESTION")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING), pytest.raises(AssistantError):
            await Gateway(client, "openai", "test").request("rules", [])
    assert "status=401" in caplog.text
    assert "SECRET_API_KEY" not in caplog.text
    assert "PRIVATE_USER_QUESTION" not in caplog.text
