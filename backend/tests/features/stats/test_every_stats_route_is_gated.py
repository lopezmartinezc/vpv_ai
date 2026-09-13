"""Every route on the stats router is analysis, and analysis is not public.

`/stats/{season_id}/fixtures` shipped behind `get_current_user` instead of
`require_perm(Perm.STATS)`, while the other seventeen routes were gated. The
lineup screen fetched it for everyone, so every participant saw the
fácil/media/difícil badges on their own players — the read the admin does to
decide his own eleven, handed to the people he is competing against.

The structural test is the one that matters: it fails the moment a route exists
without the gate, which is how this got in. The behavioural test pins what a
plain participant actually receives.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from src.app import create_app
from src.features.stats import router as stats
from src.shared.dependencies import get_current_user
from src.shared.permissions import Perm


def gates(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    for dep in dependant.dependencies:
        if dep.call is not None:
            yield dep.call
        yield from gates(dep)


def perms_required(route: APIRoute) -> set[Perm]:
    """The permissions `require_perm(...)` closed over, for every gate on a route."""
    found: set[Perm] = set()
    for gate in gates(route.dependant):
        if getattr(gate, "__name__", "") != "checker" or not getattr(gate, "__closure__", None):
            continue
        for cell in gate.__closure__ or ():
            value = cell.cell_contents
            if isinstance(value, tuple):
                found.update(p for p in value if isinstance(p, Perm))
    return found


def stats_routes() -> list[APIRoute]:
    routes = [r for r in stats.router.routes if isinstance(r, APIRoute)]
    assert len(routes) > 10, "a router with no routes would make this test pass for nothing"
    return routes


@pytest.mark.parametrize("route", stats_routes(), ids=lambda r: f"{r.methods}{r.path}")
def test_route_requires_the_stats_permission(route: APIRoute) -> None:
    assert Perm.STATS in perms_required(route), (
        f"{route.path} is reachable by any logged-in participant. "
        "Every route on this router must depend on require_perm(Perm.STATS)."
    )


@pytest.mark.asyncio
async def test_a_participant_cannot_read_fixture_difficulty() -> None:
    """The badges come from here. A participant asking directly gets nothing."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 125,
        "is_admin": False,
        "permissions": 0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/stats/1/fixtures?desde=6&jornadas=1")

    assert response.status_code == 403
