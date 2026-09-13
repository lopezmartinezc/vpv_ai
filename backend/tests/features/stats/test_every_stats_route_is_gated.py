"""Every route on the stats router is the creator's own analytics — admin only.

Two stages. `/stats/{season_id}/fixtures` first shipped open to every logged-in
participant (fixed in #135 by requiring Perm.STATS like its neighbours). Then the
question became who Perm.STATS is for: it is a delegable bit, and it opened the
whole draft preparation — valuation, history, predictions, fixture difficulty —
while the live draft board, showing the same data, was already admin only.

The creator's decision (13/09): all of it is his, not a task to delegate. So
every route here requires the administrator, and a STATS delegate gets nothing.

The structural test is the one that matters: it fails the moment a route exists
without the admin gate. The behavioural test pins what a STATS delegate receives.
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
from src.shared.dependencies import get_current_admin, get_current_user
from src.shared.permissions import Perm


def gates(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    for dep in dependant.dependencies:
        if dep.call is not None:
            yield dep.call
        yield from gates(dep)


def stats_routes() -> list[APIRoute]:
    routes = [r for r in stats.router.routes if isinstance(r, APIRoute)]
    assert len(routes) > 10, "a router with no routes would make this test pass for nothing"
    return routes


@pytest.mark.parametrize("route", stats_routes(), ids=lambda r: f"{r.methods}{r.path}")
def test_route_requires_the_administrator(route: APIRoute) -> None:
    assert get_current_admin in set(gates(route.dependant)), (
        f"{route.path} does not require the administrator. Analytics is the "
        "creator's own: every route on this router must depend on get_current_admin."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/stats/1/fixtures?desde=6&jornadas=1",
        "/api/stats/1/predictions",
        "/api/stats/1/players/draft-value",
        "/api/stats/1/players",
    ],
)
async def test_a_stats_delegate_reads_none_of_it(path: str) -> None:
    """Holding Perm.STATS used to open the whole draft preparation."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "125",
        "is_admin": False,
        "permissions": int(Perm.STATS),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(path)

    assert response.status_code == 403
