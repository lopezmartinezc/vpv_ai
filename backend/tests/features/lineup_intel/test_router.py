"""The availability is the admin's: nobody else reads or refreshes it."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.auth.service import _create_token
from src.features.lineup_intel import service as intel
from src.shared.models.season import Season
from src.shared.models.user import User
from tests.features.lineup_intel.test_service import FakeClient


async def person(db: AsyncSession, name: str, *, admin: bool = False) -> User:
    user = User(
        username=f"{name}{uuid.uuid4().hex[:6]}",
        display_name=name,
        password_hash="x",
        is_admin=admin,
        session_id=str(uuid.uuid4()),
    )
    db.add(user)
    await db.flush()
    return user


def token(user: User) -> dict[str, str]:
    assert user.session_id is not None
    return {"Authorization": f"Bearer {_create_token(user, user.session_id)}"}


@pytest.fixture
async def season(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> Season:
    season = Season(name="2026-2027", status="active", matchday_start=6, matchday_end=38)
    db_session.add(season)
    await db_session.flush()
    FakeClient.pages = {}
    monkeypatch.setattr(intel, "ScrapingClient", FakeClient)
    intel._last_manual_refresh.clear()
    return season


async def test_a_participant_can_neither_read_nor_refresh(
    client: AsyncClient, db_session: AsyncSession, season: Season
) -> None:
    someone = await person(db_session, "Jugador")
    base = f"/api/lineup-intel/{season.id}/6"
    assert (await client.get(base, headers=token(someone))).status_code == 403
    assert (await client.post(f"{base}/refresh", headers=token(someone))).status_code == 403
    assert (await client.get(base)).status_code in (401, 403)


async def test_the_admin_reads_and_refreshes_once_per_ten_minutes(
    client: AsyncClient, db_session: AsyncSession, season: Season, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[tuple[int, int]] = []
    monkeypatch.setattr(intel, "start_background_refresh", lambda s, m: started.append((s, m)))
    admin = await person(db_session, "Admin", admin=True)
    base = f"/api/lineup-intel/{season.id}/6"
    read = await client.get(base, headers=token(admin))
    assert read.status_code == 200
    assert read.json()["players"] == []

    first = await client.post(f"{base}/refresh", headers=token(admin))
    # Answered at once; the reading goes on in the background.
    assert first.status_code == 202
    assert first.json()["started"] is True
    assert started == [(season.id, 6)]
    again = await client.post(f"{base}/refresh", headers=token(admin))
    assert again.status_code == 422
    assert started == [(season.id, 6)]
