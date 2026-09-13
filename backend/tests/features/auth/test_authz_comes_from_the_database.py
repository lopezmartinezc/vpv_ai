"""Revoking a permission must bite on the next request, not in eight hours.

`get_current_user` already loaded the user row to validate `session_id`, then
returned the JWT payload and threw the row away. `require_perm` and
`get_current_admin` therefore read `is_admin` and `permissions` out of the
token, which lives for `jwt_expire_minutes` — 480. Taking someone's
administrator flag away left them administrator for the rest of the working
day, and `is_admin` bypasses every permission check there is.

Point 2.5 of docs/AUDITORIA_ADMIN.md. The row was already in hand, so reading
authorisation from it costs no extra query.

These go through the real app with real signed tokens, because the thing under
test is precisely that a *valid* token no longer decides what you may do.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.auth.service import _create_token
from src.shared.models.user import User
from src.shared.permissions import Perm

# Any gated route works; this one is cheap and needs no season to exist,
# because authorisation is checked before the handler runs.
GATED = "/api/stats/1/fixtures?desde=1&jornadas=1"
FORBIDDEN = 403


async def make_user(db: AsyncSession, *, is_admin: bool, permissions: int) -> tuple[User, str]:
    """A user and a token minted from the state they had at login."""
    user = User(
        username=f"u{uuid.uuid4().hex[:8]}",
        display_name="Prueba",
        password_hash="x",
        is_admin=is_admin,
        permissions=permissions,
        session_id=str(uuid.uuid4()),
    )
    db.add(user)
    await db.flush()
    assert user.session_id is not None
    return user, _create_token(user, user.session_id)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_revoking_a_permission_takes_effect_on_the_next_request(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, token = await make_user(db_session, is_admin=False, permissions=int(Perm.STATS))

    user.permissions = 0
    await db_session.flush()

    assert (await client.get(GATED, headers=auth(token))).status_code == FORBIDDEN


@pytest.mark.asyncio
async def test_revoking_is_admin_takes_effect_on_the_next_request(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The one that matters most: is_admin skips every permission check."""
    user, token = await make_user(db_session, is_admin=True, permissions=0)

    user.is_admin = False
    await db_session.flush()

    assert (await client.get(GATED, headers=auth(token))).status_code == FORBIDDEN


@pytest.mark.asyncio
async def test_granting_a_permission_also_takes_effect_without_a_new_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Pins that the fix reads the row rather than caching the token's claims —
    an implementation that only ever narrows would pass the two tests above."""
    user, token = await make_user(db_session, is_admin=False, permissions=0)
    assert (await client.get(GATED, headers=auth(token))).status_code == FORBIDDEN

    user.permissions = int(Perm.STATS)
    await db_session.flush()

    assert (await client.get(GATED, headers=auth(token))).status_code != FORBIDDEN


@pytest.mark.asyncio
async def test_an_untouched_permission_still_works(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The guard must not break the ordinary case."""
    _, token = await make_user(db_session, is_admin=False, permissions=int(Perm.STATS))

    assert (await client.get(GATED, headers=auth(token))).status_code != FORBIDDEN


@pytest.mark.asyncio
async def test_a_deleted_user_is_rejected_even_on_a_valid_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The row is now always loaded, so a token for a user who no longer exists
    is refused rather than trusted for its claims."""
    user, token = await make_user(db_session, is_admin=True, permissions=0)

    await db_session.delete(user)
    await db_session.flush()

    assert (await client.get(GATED, headers=auth(token))).status_code in (401, 403)
