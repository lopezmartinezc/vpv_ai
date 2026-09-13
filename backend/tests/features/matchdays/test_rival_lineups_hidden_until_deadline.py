"""A rival's lineup stays hidden until the deadline — for everyone but its owner.

`GET /api/matchdays/{season}/{number}/lineup/{participant}` asked for no session
and looked at no clock. Anyone, without logging in, could read a rival's eleven
before the deadline and copy or counter it. The matchday detail, handed to anyone
by the dashboard, also carried every participant's formation.

The rule, decided by the creator (13/09): hidden until the effective deadline,
except to the owner and to whoever may already edit lineups (admin,
LINEUPS_ADMIN). Afterwards, or once the jornada is played, anyone.

Two traps pinned here. Seasons migrated from the old site mark played jornadas
"completed", not "finished", and almost none carry a deadline — treating only
"finished" as over would have hidden every lineup of every past season. And a
bad token must count as no token: a 401 makes the frontend drop the session.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.auth.service import _create_token
from src.shared.lineup_deadline import effective_deadline, lineups_are_public
from src.shared.models.lineup import Lineup
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.season import Season
from src.shared.models.user import User
from src.shared.permissions import Perm

FORBIDDEN = 403


async def person(db: AsyncSession, name: str, *, admin: bool = False, perms: int = 0) -> User:
    user = User(
        username=f"{name}{uuid.uuid4().hex[:6]}",
        display_name=name,
        password_hash="x",
        is_admin=admin,
        permissions=perms,
        session_id=str(uuid.uuid4()),
    )
    db.add(user)
    await db.flush()
    return user


def token(user: User) -> dict[str, str]:
    assert user.session_id is not None
    return {"Authorization": f"Bearer {_create_token(user, user.session_id)}"}


@pytest.fixture
async def scene(db_session: AsyncSession) -> dict:
    """J6 not played yet, deadline two days away, the owner has fielded a side."""
    season = Season(
        name="2026-2027",
        status="active",
        matchday_start=6,
        matchday_current=6,
        matchday_end=38,
        lineup_deadline_min=30,
    )
    db_session.add(season)
    await db_session.flush()

    owner_user = await person(db_session, "Owner")
    rival_user = await person(db_session, "Rival")
    owner = SeasonParticipant(season_id=season.id, user_id=owner_user.id)
    rival = SeasonParticipant(season_id=season.id, user_id=rival_user.id)
    db_session.add_all([owner, rival])
    await db_session.flush()

    matchday = Matchday(
        season_id=season.id,
        number=6,
        status="pending",
        stats_ok=False,
        first_match_at=datetime.now(UTC) + timedelta(days=2),
    )
    db_session.add(matchday)
    await db_session.flush()

    db_session.add(
        Lineup(
            participant_id=owner.id, matchday_id=matchday.id, formation="1-4-4-2", confirmed=True
        )
    )
    await db_session.flush()
    return {
        "season": season,
        "matchday": matchday,
        "owner": owner,
        "rival": rival,
        "owner_user": owner_user,
        "rival_user": rival_user,
    }


def url(scene: dict, participant: SeasonParticipant | None = None) -> str:
    who = participant or scene["owner"]
    return f"/api/matchdays/{scene['season'].id}/6/lineup/{who.id}"


async def open_the_deadline(db: AsyncSession, scene: dict) -> None:
    scene["matchday"].first_match_at = datetime.now(UTC) - timedelta(hours=1)
    await db.flush()


# --- before the deadline -----------------------------------------------------


async def test_nobody_logged_out_reads_a_lineup_before_the_deadline(
    client: AsyncClient, scene: dict
) -> None:
    assert (await client.get(url(scene))).status_code == FORBIDDEN


async def test_a_rival_reads_no_lineup_before_the_deadline(
    client: AsyncClient, scene: dict
) -> None:
    response = await client.get(url(scene), headers=token(scene["rival_user"]))
    assert response.status_code == FORBIDDEN


async def test_the_owner_always_reads_his_own(client: AsyncClient, scene: dict) -> None:
    response = await client.get(url(scene), headers=token(scene["owner_user"]))
    assert response.status_code == 200
    assert response.json()["formation"] == "1-4-4-2"


async def test_an_admin_reads_it(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    admin = await person(db_session, "Admin", admin=True)
    assert (await client.get(url(scene), headers=token(admin))).status_code == 200


async def test_a_lineups_delegate_reads_it(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    """Whoever may already edit a lineup may read it."""
    delegate = await person(db_session, "Delegado", perms=int(Perm.LINEUPS_ADMIN))
    assert (await client.get(url(scene), headers=token(delegate))).status_code == 200


async def test_a_refusal_does_not_reveal_whether_a_side_was_fielded(
    client: AsyncClient, scene: dict
) -> None:
    """The rival has no lineup. Before the deadline that must look the same as
    one he does have — 403, not 404 — or the status code leaks it."""
    response = await client.get(url(scene, scene["rival"]), headers=token(scene["owner_user"]))
    assert response.status_code == FORBIDDEN


async def test_a_bad_token_is_treated_as_no_token_not_as_401(
    client: AsyncClient, scene: dict
) -> None:
    """A 401 makes the frontend clear the session and jump to /login."""
    response = await client.get(url(scene), headers={"Authorization": "Bearer caducado"})
    assert response.status_code == FORBIDDEN


async def test_the_public_matchday_detail_hides_formations_before_the_deadline(
    client: AsyncClient, scene: dict
) -> None:
    response = await client.get(f"/api/matchdays/{scene['season'].id}/6")
    assert response.status_code == 200
    assert all(s["formation"] is None for s in response.json()["scores"])


# --- after the deadline ------------------------------------------------------


async def test_anyone_reads_it_once_the_deadline_has_passed(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    await open_the_deadline(db_session, scene)
    assert (await client.get(url(scene))).status_code == 200


async def test_formations_show_once_the_deadline_has_passed(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    await open_the_deadline(db_session, scene)
    response = await client.get(f"/api/matchdays/{scene['season'].id}/6")
    assert "1-4-4-2" in [s["formation"] for s in response.json()["scores"]]


async def test_a_migrated_completed_jornada_without_a_deadline_is_public(
    client: AsyncClient, db_session: AsyncSession, scene: dict
) -> None:
    """304 migrated jornadas are "completed" and 293 carry no deadline at all."""
    scene["matchday"].status = "completed"
    scene["matchday"].first_match_at = None
    await db_session.flush()
    assert (await client.get(url(scene))).status_code == 200


# --- the rule itself -----------------------------------------------------------


class _Md:
    def __init__(self, **kw: object) -> None:
        self.status = kw.get("status", "pending")
        self.stats_ok = kw.get("stats_ok", False)
        self.deadline_at = kw.get("deadline_at")
        self.first_match_at = kw.get("first_match_at")


NOW = datetime(2026, 9, 15, 18, 0, tzinfo=UTC)


def test_the_override_wins_over_the_computed_deadline() -> None:
    override = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    md = _Md(deadline_at=override, first_match_at=datetime(2026, 9, 15, 20, 0, tzinfo=UTC))
    assert effective_deadline(md, 30) == override


def test_the_computed_deadline_is_kick_off_minus_the_margin() -> None:
    md = _Md(first_match_at=datetime(2026, 9, 15, 20, 0, tzinfo=UTC))
    assert effective_deadline(md, 30) == datetime(2026, 9, 15, 19, 30, tzinfo=UTC)


def test_a_naive_deadline_is_read_as_utc() -> None:
    md = _Md(deadline_at=datetime(2026, 9, 15, 12, 0))
    assert effective_deadline(md, 30) == datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def test_lineups_open_exactly_at_the_deadline() -> None:
    md = _Md(deadline_at=NOW)
    assert lineups_are_public(md, 30, now=NOW) is True
    assert lineups_are_public(md, 30, now=NOW - timedelta(seconds=1)) is False


def test_no_deadline_information_keeps_an_open_jornada_closed() -> None:
    assert lineups_are_public(_Md(), 30, now=NOW) is False


@pytest.mark.parametrize("status", ["finished", "completed"])
def test_a_played_jornada_is_public_whatever_its_status_is_called(status: str) -> None:
    assert lineups_are_public(_Md(status=status), 30, now=NOW) is True


def test_stats_being_in_means_the_jornada_was_played() -> None:
    assert lineups_are_public(_Md(stats_ok=True), 30, now=NOW) is True
