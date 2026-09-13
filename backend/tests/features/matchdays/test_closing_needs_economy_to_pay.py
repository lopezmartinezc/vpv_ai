"""Closing a jornada that would pay out needs ECONOMY as well as MATCHDAYS.

Closing generates the weekly payments, but the endpoint only asked for
MATCHDAYS: a delegate for matchdays could move money on his own. Decided by the
creator (13/09): when the dry run says the close would generate payments,
ECONOMY is required too. When it would not, MATCHDAYS is enough.

The panel is told the same thing through the state endpoint, so it relays the
server's answer rather than working it out.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.auth.service import _create_token
from src.shared.models.matchday import Match, Matchday
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.user import User
from src.shared.permissions import Perm


async def person(db: AsyncSession, *, admin: bool = False, perms: int = 0) -> dict[str, str]:
    user = User(
        username=f"u{uuid.uuid4().hex[:8]}",
        display_name="Prueba",
        password_hash="x",
        is_admin=admin,
        permissions=perms,
        session_id=str(uuid.uuid4()),
    )
    db.add(user)
    await db.flush()
    assert user.session_id is not None
    return {"Authorization": f"Bearer {_create_token(user, user.session_id)}"}


@pytest.fixture
async def scene(db_session: AsyncSession) -> dict:
    """A jornada ready to close, in a season that pays weekly."""
    season = Season(
        name="2026-2027",
        status="active",
        matchday_start=1,
        matchday_current=5,
        matchday_end=38,
        matchday_scanned=4,
        weekly_payments_enabled=True,
    )
    db_session.add(season)
    await db_session.flush()
    home = Team(season_id=season.id, name="Celta", slug="celta")
    away = Team(season_id=season.id, name="Málaga", slug="malaga")
    db_session.add_all([home, away])
    await db_session.flush()
    matchday = Matchday(season_id=season.id, number=5, status="pending")
    db_session.add(matchday)
    await db_session.flush()
    db_session.add(
        Match(
            matchday_id=matchday.id,
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=1,
            away_score=0,
            stats_ok=True,
        )
    )
    await db_session.flush()
    return {"season": season, "matchday": matchday}


def paths(scene: dict) -> tuple[str, str]:
    base = f"/api/matchdays/admin/{scene['season'].id}/5"
    return f"{base}/estado", f"{base}/cerrar"


async def test_a_matchdays_delegate_cannot_close_one_that_pays(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    _, close = paths(scene)
    headers = await person(db_session, perms=int(Perm.MATCHDAYS))

    response = await client.post(close, headers=headers)

    assert response.status_code == 403
    assert "Economía" in response.json()["message"]
    await db_session.refresh(scene["matchday"])
    assert scene["matchday"].status == "pending"


async def test_the_state_tells_the_panel_why(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    state, _ = paths(scene)
    headers = await person(db_session, perms=int(Perm.MATCHDAYS))

    body = (await client.get(state, headers=headers)).json()

    assert body["can_close"] is True
    assert body["requires_economy"] is True
    assert "Economía" in body["missing_permission"]


async def test_matchdays_and_economy_together_may_close_it(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    _, close = paths(scene)
    headers = await person(db_session, perms=int(Perm.MATCHDAYS | Perm.ECONOMY))

    response = await client.post(close, headers=headers)

    assert response.status_code == 200
    assert response.json()["closed"] is True


async def test_an_admin_may_close_it(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    _, close = paths(scene)
    assert (
        await client.post(close, headers=await person(db_session, admin=True))
    ).status_code == 200


async def test_when_nothing_is_paid_matchdays_is_enough(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    """A season with no weekly payments: closing moves no money, so no ECONOMY."""
    scene["season"].weekly_payments_enabled = False
    await db_session.flush()
    state, close = paths(scene)
    headers = await person(db_session, perms=int(Perm.MATCHDAYS))

    assert (await client.get(state, headers=headers)).json()["missing_permission"] is None
    assert (await client.post(close, headers=headers)).status_code == 200
