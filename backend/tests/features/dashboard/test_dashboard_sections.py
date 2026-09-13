"""A section that fails must not look like a section with no data (IN-02).

The dashboard gathers four blocks in parallel with return_exceptions=True and
turned every exception into None, logging nothing. The home page then showed an
empty ranking or no economy as though there were simply nothing to show, and
nobody could tell a broken query from an empty season.

Absence and failure are now different: a missing resource stays None and silent;
anything else is logged and named in ``unavailable``.
"""

from __future__ import annotations

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app
from src.core.exceptions import NotFoundError
from src.features.dashboard import router as dashboard


async def _none(*_: object, **__: object) -> None:
    return None


async def _boom(*_: object, **__: object) -> None:
    raise RuntimeError("la consulta de economía ha fallado")


async def _missing(*_: object, **__: object) -> None:
    raise NotFoundError("Copa", 12)


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch):
    """Four services that touch no database: standings and matchday have no data,
    the copa does not exist for this season, the economy query breaks."""
    monkeypatch.setattr(dashboard.StandingsService, "get_standings", _none)
    monkeypatch.setattr(dashboard.MatchdayService, "get_matchday_detail", _none)
    monkeypatch.setattr(dashboard.CopaService, "get_copa_full", _missing)
    monkeypatch.setattr(dashboard.EconomyService, "get_overview", _boom)


async def _get() -> dict:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as ac:
        response = await ac.get("/api/dashboard/12?matchday_current=6")
    assert response.status_code == 200, "one failing section must not take the page down"
    return response.json()


@pytest.mark.asyncio
async def test_a_failing_section_is_named(patched) -> None:
    assert (await _get())["unavailable"] == ["economy"]


@pytest.mark.asyncio
async def test_a_missing_section_is_absence_not_failure(patched) -> None:
    body = await _get()
    assert body["copa"] is None
    assert "copa" not in body["unavailable"]


@pytest.mark.asyncio
async def test_the_failure_is_logged(patched, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="src.features.dashboard.router"):
        await _get()
    assert any("economy" in r.getMessage() and r.exc_info for r in caplog.records)


def test_settle_keeps_a_real_value() -> None:
    assert dashboard.settle("standings", {"x": 1}, 12) == ({"x": 1}, False)
