"""Who pays what each matchday, and when a matchday may be paid at all.

J6 of 2026-27 was paid with the points half in: whoever was still on zero tied
with the last one and was charged his amount, so the winner of the matchday
paid the 2 € of the last place.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.economy.repository import MatchdayRankingRow
from src.features.economy.service import EconomyService, compute_weekly_amounts
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.season import Season, SeasonPayment
from src.shared.models.transaction import Transaction
from src.shared.models.user import User

# 1st to 3rd pay nothing, the last ones pay, as the real table does.
RULES = {1: Decimal("0"), 2: Decimal("0"), 3: Decimal("0"), 4: Decimal("1"), 5: Decimal("2")}


def ranked(*points: int) -> list[MatchdayRankingRow]:
    return [
        MatchdayRankingRow(participant_id=i, ranking=i, total_points=p)
        for i, p in enumerate(points, start=1)
    ]


def test_each_position_pays_its_own_amount() -> None:
    amounts = compute_weekly_amounts(ranked(90, 80, 70, 60, 50), RULES)
    assert amounts == [
        (1, Decimal("0")),
        (2, Decimal("0")),
        (3, Decimal("0")),
        (4, Decimal("1")),
        (5, Decimal("2")),
    ]


def test_those_tied_on_points_pay_the_same_the_worse_of_them_pays() -> None:
    # 4th and 5th tie: both pay the 5th's 2 €. 1st and 2nd tie: both pay 0.
    amounts = compute_weekly_amounts(ranked(90, 90, 70, 50, 50), RULES)
    assert [a for _, a in amounts] == [
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("2"),
        Decimal("2"),
    ]


def test_everyone_on_the_same_points_would_pay_the_last_ones_amount() -> None:
    # Which is why the service refuses to pay a matchday in that state.
    assert [a for _, a in compute_weekly_amounts(ranked(0, 0, 0, 0, 0), RULES)] == [
        Decimal("2")
    ] * 5


@pytest.fixture
async def league(db_session: AsyncSession) -> dict:
    season = Season(
        name="2026-2027",
        status="active",
        kind="league",
        matchday_start=6,
        matchday_end=38,
        total_participants=5,
        weekly_payments_enabled=True,
    )
    db_session.add(season)
    await db_session.flush()
    db_session.add_all(
        SeasonPayment(
            season_id=season.id,
            payment_type="weekly_position",
            position_rank=rank,
            amount=amount,
        )
        for rank, amount in RULES.items()
    )
    parts = []
    for i in range(5):
        user = User(username=f"u{i}", password_hash="x", display_name=f"U{i}")
        db_session.add(user)
        await db_session.flush()
        part = SeasonParticipant(season_id=season.id, user_id=user.id)
        db_session.add(part)
        parts.append(part)
    matchday = Matchday(season_id=season.id, number=6, status="pending", stats_ok=False)
    db_session.add(matchday)
    await db_session.flush()
    # The winner first, as the ranking has them.
    for place, (part, points) in enumerate(zip(parts, [90, 80, 70, 60, 50], strict=True), start=1):
        db_session.add(
            ParticipantMatchdayScore(
                participant_id=part.id,
                matchday_id=matchday.id,
                total_points=points,
                ranking=place,
            )
        )
    await db_session.flush()
    return {"season": season, "matchday": matchday, "parts": parts}


async def paid(db: AsyncSession, matchday_id: int) -> dict[int, Decimal]:
    rows = await db.execute(
        select(Transaction).where(
            Transaction.matchday_id == matchday_id, Transaction.type == "weekly_payment"
        )
    )
    return {t.participant_id: t.amount for t in rows.scalars()}


async def test_a_matchday_without_its_stats_is_not_paid(
    db_session: AsyncSession, league: dict
) -> None:
    service = EconomyService(db_session)
    created = await service.generate_weekly_payments(league["season"].id, league["matchday"].id)
    assert created == 0
    assert await paid(db_session, league["matchday"].id) == {}


async def test_once_the_stats_are_in_each_position_pays_its_amount(
    db_session: AsyncSession, league: dict
) -> None:
    league["matchday"].stats_ok = True
    await db_session.flush()
    service = EconomyService(db_session)
    created = await service.generate_weekly_payments(league["season"].id, league["matchday"].id)
    await db_session.flush()
    amounts = await paid(db_session, league["matchday"].id)
    # Only who pays gets a row: the first three pay nothing.
    assert created == 2
    assert amounts == {
        league["parts"][3].id: Decimal("1.00"),
        league["parts"][4].id: Decimal("2.00"),
    }


async def test_a_matchday_with_everyone_on_the_same_points_is_not_paid(
    db_session: AsyncSession, league: dict
) -> None:
    league["matchday"].stats_ok = True
    for row in (
        await db_session.execute(
            select(ParticipantMatchdayScore).where(
                ParticipantMatchdayScore.matchday_id == league["matchday"].id
            )
        )
    ).scalars():
        row.total_points = 0
    await db_session.flush()
    service = EconomyService(db_session)
    assert await service.generate_weekly_payments(league["season"].id, league["matchday"].id) == 0
    assert await paid(db_session, league["matchday"].id) == {}


async def test_regenerating_before_the_stats_leaves_what_is_there(
    db_session: AsyncSession, league: dict
) -> None:
    # An admin editing a lineup regenerates the payments of that matchday.
    league["matchday"].stats_ok = True
    await db_session.flush()
    service = EconomyService(db_session)
    await service.generate_weekly_payments(league["season"].id, league["matchday"].id)
    await db_session.flush()
    before = await paid(db_session, league["matchday"].id)

    league["matchday"].stats_ok = False
    await db_session.flush()
    assert (
        await service.regenerate_weekly_payments(league["season"].id, league["matchday"].id) == 0
    )
    assert await paid(db_session, league["matchday"].id) == before
