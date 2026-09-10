"""Only an administrator can reach either draft chat. Every route, every time.

Two layers, because each catches what the other cannot:

- Structural: walk the dependency tree of every route on both routers and
  demand the admin gate. This is what survives the next endpoint someone adds
  in a hurry — the test fails the moment a route exists without the gate,
  before anyone has to think of testing it.
- Behavioural (V1, over HTTP with real signed tokens): a logged-in
  participant and a draft manager holding Perm.DRAFT both get 403. The draft
  manager matters most: `require_perm(Perm.DRAFT)` would let him in, and it
  is the dependency someone might reach for by habit. `get_current_admin`
  checks `is_admin` alone, and this pins that.

V2's `admin_id` resolves the user through `AsyncSessionLocal`, bound to the
real database rather than the test one, so its 401/403 behaviour is proven in
its own unit tests with the session mocked; here it gets the structural
guarantee plus the anonymous path through the real app, which also proves the
AssistantError handler is wired into `create_app` (a 401, not a 500).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.auth.service import _create_token
from src.features.draft_assistant import router as v1
from src.features.draft_assistant_v2 import auth as v2_auth
from src.features.draft_assistant_v2 import router as v2
from src.shared.dependencies import get_current_admin
from src.shared.models.user import User
from src.shared.permissions import Perm

AUTH_REJECTED = {401, 403}
PLACEHOLDERS = {"{season_id}": "1", "{phase}": "preseason", "{draft_id}": "1"}


def gates(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    for dep in dependant.dependencies:
        if dep.call is not None:
            yield dep.call
        yield from gates(dep)


def api_routes(router: Any) -> list[APIRoute]:
    routes = [r for r in router.routes if isinstance(r, APIRoute)]
    assert routes, "a router with no routes would make this test pass for nothing"
    return routes


def concrete_path(route: APIRoute, prefix: str) -> str:
    path = prefix + route.path
    for placeholder, value in PLACEHOLDERS.items():
        path = path.replace(placeholder, value)
    assert "{" not in path, f"unfilled placeholder in {path}"
    return path


# --------------------------------------------------------------------------
# Structural: every route on both routers hangs off the admin gate.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "route", api_routes(v1.router), ids=lambda r: f"{sorted(r.methods)} {r.path}"
)
def test_every_v1_route_requires_admin(route: APIRoute) -> None:
    assert get_current_admin in list(gates(route.dependant)), route.path


@pytest.mark.parametrize(
    "route", api_routes(v2.router), ids=lambda r: f"{sorted(r.methods)} {r.path}"
)
def test_every_v2_route_requires_admin(route: APIRoute) -> None:
    assert v2_auth.admin_id in list(gates(route.dependant)), route.path


# --------------------------------------------------------------------------
# Behavioural: real tokens against the real app.
# --------------------------------------------------------------------------


async def persisted_user(
    db: AsyncSession, *, is_admin: bool, permissions: int
) -> tuple[User, str]:
    """A user the request pipeline will find, with the session the token names."""
    session_id = str(uuid.uuid4())
    user = User(
        username=f"u-{session_id[:8]}",
        password_hash="x",
        display_name="Test",
        is_admin=is_admin,
        permissions=permissions,
        session_id=session_id,
    )
    db.add(user)
    await db.flush()
    return user, _create_token(user, session_id)


def v1_requests() -> list[tuple[str, str]]:
    return [
        (method, concrete_path(route, "/api"))
        for route in api_routes(v1.router)
        for method in sorted(route.methods)
    ]


async def call(client: AsyncClient, method: str, path: str, token: str | None) -> int:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = {"question": "¿mejor delantero?", "provider": "openai", "model": "gpt-5"}
    response = await client.request(
        method, path, headers=headers, json=body if method == "POST" else None
    )
    return response.status_code


@pytest.mark.asyncio
async def test_v1_rejects_anonymous_on_every_route(client: AsyncClient) -> None:
    for method, path in v1_requests():
        assert await call(client, method, path, None) in AUTH_REJECTED, f"{method} {path}"


@pytest.mark.asyncio
async def test_v1_rejects_a_logged_in_participant(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, token = await persisted_user(db_session, is_admin=False, permissions=0)
    for method, path in v1_requests():
        assert await call(client, method, path, token) == 403, f"{method} {path}"


@pytest.mark.asyncio
async def test_v1_rejects_a_draft_manager(client: AsyncClient, db_session: AsyncSession) -> None:
    """The one that would slip through `require_perm(Perm.DRAFT)`."""
    _, token = await persisted_user(db_session, is_admin=False, permissions=int(Perm.DRAFT))
    for method, path in v1_requests():
        assert await call(client, method, path, token) == 403, f"{method} {path}"


@pytest.mark.asyncio
async def test_v1_admits_an_admin_past_the_gate(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Not asserting success — the assistant may be disabled or unconfigured
    in tests — only that the answer is never an authentication rejection."""
    _, token = await persisted_user(db_session, is_admin=True, permissions=0)
    for method, path in v1_requests():
        assert await call(client, method, path, token) not in AUTH_REJECTED, f"{method} {path}"


@pytest.mark.asyncio
async def test_v2_rejects_anonymous_through_the_real_app(client: AsyncClient) -> None:
    """Also proves the V2 error handler is wired in create_app: 401, not 500."""
    for route in api_routes(v2.router):
        for method in sorted(route.methods):
            path = concrete_path(route, "/api")
            status = await call(client, method, path, None)
            assert status == 401, f"{method} {path} -> {status}"
