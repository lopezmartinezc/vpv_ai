"""Auto-pick has to be able to open the draft, not only continue it.

``_maybe_auto_pick`` was reached from exactly one place: the end of
``add_pick``. So the chain could only ever be *continued* by a pick somebody
else had already made — pick #1 had nothing before it to set it off. If the
first manager in the order was away with an auto-pick list ready, the draft
simply sat there until an admin picked for them by hand.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.drafts.service import DraftService
from src.features.drafts.wishlist_schemas import WishlistUpsertRequest
from src.shared.models.draft import DraftPick
from src.shared.models.draft_wishlist import DraftWishlist, DraftWishlistPlayer
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.user import User

ADMIN = {"is_admin": True, "permissions": 0, "sub": 1}


async def _setup(
    db: AsyncSession, n: int = 3
) -> tuple[int, list[SeasonParticipant], list[Player]]:
    season = Season(
        name="2026-2027",
        status="active",
        matchday_start=1,
        matchday_end=38,
        draft_pool_size=4,
        lineup_deadline_min=30,
        total_participants=n,
        kind="league",
    )
    db.add(season)
    await db.flush()

    users = [User(username=f"a{i}", password_hash="x", display_name=f"A{i}") for i in range(n)]
    db.add_all(users)
    await db.flush()
    parts = [
        SeasonParticipant(season_id=season.id, user_id=users[i].id, draft_order=i + 1)
        for i in range(n)
    ]
    db.add_all(parts)
    await db.flush()

    team = Team(season_id=season.id, name="T", slug="t")
    db.add(team)
    await db.flush()
    players = [
        Player(
            season_id=season.id,
            team_id=team.id,
            name=f"P{i}",
            display_name=f"P{i}",
            slug=f"p{i}",
            position="MED",
        )
        for i in range(n * 4)
    ]
    db.add_all(players)
    await db.flush()

    svc = DraftService(db)
    draft = await svc.create_draft(season.id, "preseason", "snake")
    return draft.id, parts, players


async def _wishlist(db: AsyncSession, draft_id: int, participant_id: int, player: Player) -> None:
    wl = DraftWishlist(draft_id=draft_id, participant_id=participant_id, enabled=True)
    db.add(wl)
    await db.flush()
    db.add(DraftWishlistPlayer(wishlist_id=wl.id, player_id=player.id, priority=1))
    await db.flush()


async def _picks(db: AsyncSession, draft_id: int) -> list[DraftPick]:
    rows = await db.execute(
        select(DraftPick).where(DraftPick.draft_id == draft_id).order_by(DraftPick.pick_number)
    )
    return list(rows.scalars().all())


@pytest.mark.asyncio
async def test_starting_the_draft_resolves_the_very_first_pick(db_session: AsyncSession) -> None:
    """The reported gap: nobody has picked, so nothing triggers the chain."""
    draft_id, parts, players = await _setup(db_session)
    await _wishlist(db_session, draft_id, parts[0].id, players[0])
    svc = DraftService(db_session)

    assert await _picks(db_session, draft_id) == []

    await svc.set_draft_status(draft_id, "start")

    picks = await _picks(db_session, draft_id)
    assert len(picks) >= 1
    assert picks[0].pick_number == 1
    assert picks[0].player_id == players[0].id
    assert picks[0].participant_id == parts[0].id


@pytest.mark.asyncio
async def test_starting_chains_through_consecutive_absentees(db_session: AsyncSession) -> None:
    draft_id, parts, players = await _setup(db_session)
    await _wishlist(db_session, draft_id, parts[0].id, players[0])
    await _wishlist(db_session, draft_id, parts[1].id, players[1])

    await DraftService(db_session).set_draft_status(draft_id, "start")

    picks = await _picks(db_session, draft_id)
    assert [p.pick_number for p in picks[:2]] == [1, 2]
    assert picks[1].participant_id == parts[1].id


@pytest.mark.asyncio
async def test_start_leaves_the_turn_alone_when_nobody_has_a_list(
    db_session: AsyncSession,
) -> None:
    draft_id, _parts, _players = await _setup(db_session)

    draft = await DraftService(db_session).set_draft_status(draft_id, "start")

    assert draft.status == "in_progress"
    assert await _picks(db_session, draft_id) == []


@pytest.mark.asyncio
async def test_resuming_picks_up_a_turn_that_was_waiting(db_session: AsyncSession) -> None:
    """Un-pausing has the same problem: the turn it stopped on needs resolving."""
    draft_id, parts, players = await _setup(db_session)
    svc = DraftService(db_session)
    await svc.set_draft_status(draft_id, "pause")
    await _wishlist(db_session, draft_id, parts[0].id, players[0])

    await svc.set_draft_status(draft_id, "resume")

    assert len(await _picks(db_session, draft_id)) >= 1


@pytest.mark.asyncio
async def test_a_paused_draft_never_auto_picks(db_session: AsyncSession) -> None:
    draft_id, parts, players = await _setup(db_session)
    svc = DraftService(db_session)
    await _wishlist(db_session, draft_id, parts[0].id, players[0])

    await svc.set_draft_status(draft_id, "pause")
    await svc.set_draft_status(draft_id, "pause")

    assert await _picks(db_session, draft_id) == []


@pytest.mark.asyncio
async def test_saving_a_list_on_your_own_turn_fires_it(db_session: AsyncSession) -> None:
    """Setting up auto-pick while it is already your turn should act at once —
    otherwise it waits for a pick that, by definition, is yours to make."""
    draft_id, parts, players = await _setup(db_session)
    svc = DraftService(db_session)
    await svc.set_draft_status(draft_id, "start")

    user = {"sub": parts[0].user_id, "is_admin": False, "permissions": 0}
    await svc.upsert_my_wishlist(
        draft_id,
        user,
        WishlistUpsertRequest(enabled=True, player_ids=[players[0].id]),
    )

    picks = await _picks(db_session, draft_id)
    assert len(picks) >= 1
    assert picks[0].player_id == players[0].id
