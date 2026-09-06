"""A test draft can be run and then fully reset by deleting its picks.

Assurance for the workflow "create a draft, test it, wipe it, do the real
one": deleting every pick releases each player's ownership
(``players.owner_id`` back to NULL) and reopens a completed draft, leaving a
clean board on the SAME draft row (there is no delete-whole-draft endpoint,
and create_draft allows only one draft per season+phase).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.drafts.service import DraftService
from src.shared.models.draft import Draft, DraftPick
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.user import User

ADMIN = {"is_admin": True, "permissions": 0, "sub": 1}


@pytest.mark.asyncio
async def test_test_draft_can_be_run_and_fully_reset(db_session: AsyncSession) -> None:
    # --- season with 3 participants, pool of 3 => 9 picks to complete ---
    season = Season(
        name="2026-2027", status="active", matchday_start=1, matchday_end=38,
        draft_pool_size=3, lineup_deadline_min=30, total_participants=3, kind="league",
    )
    db_session.add(season)
    await db_session.flush()

    users = [User(username=f"u{i}", password_hash="x", display_name=f"U{i}") for i in range(3)]
    db_session.add_all(users)
    await db_session.flush()
    parts = [
        SeasonParticipant(season_id=season.id, user_id=users[i].id, draft_order=i + 1)
        for i in range(3)
    ]
    db_session.add_all(parts)
    await db_session.flush()

    team = Team(season_id=season.id, name="T", slug="t")
    db_session.add(team)
    await db_session.flush()

    players = [
        Player(
            season_id=season.id, team_id=team.id, owner_id=None,
            name=f"P{i}", display_name=f"P{i}", slug=f"p{i}", position="MED",
        )
        for i in range(9)
    ]
    db_session.add_all(players)
    await db_session.flush()

    svc = DraftService(db_session)

    # --- create + run the draft to completion (admin picks the turn) ---
    created = await svc.create_draft(season.id, "preseason", "snake")
    draft_id = created.id
    for p in players:
        await svc.add_pick(draft_id, p.id, ADMIN)

    draft = await db_session.get(Draft, draft_id)
    await db_session.refresh(draft)
    assert draft.status == "completed"
    owners = (await db_session.execute(select(Player.owner_id).where(Player.season_id == season.id))).scalars().all()
    assert all(o is not None for o in owners)  # every player owned during the test

    # --- reset: delete every pick ---
    for n in range(9, 0, -1):
        await svc.delete_pick(draft_id, n, ADMIN)

    # --- clean board on the SAME draft: 0 picks, no owners, reopened ---
    remaining = (await db_session.execute(select(DraftPick).where(DraftPick.draft_id == draft_id))).scalars().all()
    assert remaining == []
    owners = (await db_session.execute(select(Player.owner_id).where(Player.season_id == season.id))).scalars().all()
    assert all(o is None for o in owners)  # ownership fully released
    await db_session.refresh(draft)
    assert draft.status != "completed"  # reopened, ready for the real draft
