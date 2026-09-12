"""The ownership flag has to survive the trip to the client, not just the query.

The repository learned to report who is already owned and a test proved it.
The endpoint rebuilds the response field by field, that list was not updated,
and the schema's default filled the gap with False for everyone — so the
checkbox hid nobody and nothing failed: no type error, no red test, because
the test covered the layer that changed rather than the path the user takes.

This one goes over HTTP, which is the only place that mistake shows.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.auth.service import _create_token
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.user import User


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict[str, str]:
    session_id = str(uuid.uuid4())
    admin = User(
        username=f"admin-{session_id[:8]}",
        password_hash="x",
        display_name="Admin",
        is_admin=True,
        session_id=session_id,
    )
    db_session.add(admin)
    await db_session.flush()
    return {"Authorization": f"Bearer {_create_token(admin, session_id)}"}


@pytest.fixture
async def seeded(db_session: AsyncSession):
    season = Season(
        name="2026-2027", matchday_start=1, matchday_current=5, matchday_end=38, kind="league"
    )
    db_session.add(season)
    await db_session.flush()
    team = Team(season_id=season.id, name="Getafe", slug="getafe")
    db_session.add(team)
    await db_session.flush()
    md = Matchday(season_id=season.id, number=1, counts=True)
    db_session.add(md)
    await db_session.flush()
    user = User(username="dueno", password_hash="x", display_name="Dueño")
    db_session.add(user)
    await db_session.flush()
    owner = SeasonParticipant(season_id=season.id, user_id=user.id, draft_order=1)
    db_session.add(owner)
    await db_session.flush()

    for slug, owner_id in (("fichado", owner.id), ("libre", None)):
        player = Player(
            season_id=season.id,
            team_id=team.id,
            name=slug,
            display_name=slug,
            slug=slug,
            position="DEF",
            owner_id=owner_id,
        )
        db_session.add(player)
        await db_session.flush()
        db_session.add(
            PlayerStat(
                player_id=player.id,
                matchday_id=md.id,
                position="DEF",
                played=True,
                minutes_played=90,
                pts_total=6,
            )
        )
    await db_session.flush()
    return season


@pytest.mark.asyncio
async def test_the_flag_reaches_the_client(client: AsyncClient, seeded, admin_headers) -> None:
    response = await client.get(f"/api/stats/{seeded.id}/players", headers=admin_headers)
    assert response.status_code == 200
    rows = {p["display_name"]: p for p in response.json()["players"]}
    assert rows["fichado"]["is_drafted"] is True
    assert rows["libre"]["is_drafted"] is False


@pytest.mark.asyncio
async def test_it_survives_the_pre_draft_view_too(
    client: AsyncClient, seeded, admin_headers
) -> None:
    """The tab asks with include_noncounting while preparing a draft — the
    exact call that matters here."""
    response = await client.get(
        f"/api/stats/{seeded.id}/players?include_noncounting=true", headers=admin_headers
    )
    rows = {p["display_name"]: p for p in response.json()["players"]}
    assert rows["fichado"]["is_drafted"] is True
