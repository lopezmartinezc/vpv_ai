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
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.season import Season, SeasonPayment
from src.shared.models.team import Team
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
    home = Team(season_id=season.id, name="Celta", slug="celta")
    away = Team(season_id=season.id, name="Elche", slug="elche")
    db_session.add_all([matchday, home, away])
    await db_session.flush()
    # One match played and scraped; the matchday's own flag is still off, as it
    # is until the close sets it.
    played = Match(
        matchday_id=matchday.id,
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=1,
        away_score=0,
        stats_ok=True,
    )
    db_session.add(played)
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
    return {
        "season": season,
        "matchday": matchday,
        "parts": parts,
        "home": home,
        "away": away,
        "played": played,
    }


async def paid(db: AsyncSession, matchday_id: int) -> dict[int, Decimal]:
    rows = await db.execute(
        select(Transaction).where(
            Transaction.matchday_id == matchday_id, Transaction.type == "weekly_payment"
        )
    )
    return {t.participant_id: t.amount for t in rows.scalars()}


async def test_a_postponed_match_that_counts_holds_the_whole_matchday_back(
    db_session: AsyncSession, league: dict
) -> None:
    # J6 of 2026-27: a match put off to the end of October, and it counts.
    others = [
        Team(season_id=league["season"].id, name="Rayo", slug="rayo"),
        Team(season_id=league["season"].id, name="Betis", slug="betis"),
    ]
    db_session.add_all(others)
    await db_session.flush()
    postponed = Match(
        matchday_id=league["matchday"].id,
        home_team_id=others[0].id,
        away_team_id=others[1].id,
        counts=True,
        stats_ok=False,
    )
    db_session.add(postponed)
    await db_session.flush()
    service = EconomyService(db_session)
    assert await service.generate_weekly_payments(league["season"].id, league["matchday"].id) == 0

    # Left out of the season's scoring, as postponed matches have been before:
    # the matchday is settled and pays.
    postponed.counts = False
    await db_session.flush()
    assert await service.generate_weekly_payments(league["season"].id, league["matchday"].id) == 2


async def test_a_matchday_with_no_counting_match_is_not_paid(
    db_session: AsyncSession, league: dict
) -> None:
    # Nothing counted that week: there is no ranking to charge by.
    league["played"].counts = False
    await db_session.flush()
    service = EconomyService(db_session)
    assert await service.generate_weekly_payments(league["season"].id, league["matchday"].id) == 0
    assert await paid(db_session, league["matchday"].id) == {}


async def test_a_matchday_whose_matches_are_all_scraped_pays_without_waiting_for_the_flag(
    db_session: AsyncSession, league: dict
) -> None:
    service = EconomyService(db_session)
    assert league["matchday"].stats_ok is False
    assert await service.generate_weekly_payments(league["season"].id, league["matchday"].id) == 2


async def test_a_matchday_without_its_stats_is_not_paid(
    db_session: AsyncSession, league: dict
) -> None:
    league["played"].stats_ok = False
    await db_session.flush()
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

    # Its match goes back to unscraped, as it is while the stats come in.
    league["matchday"].stats_ok = False
    league["played"].stats_ok = False
    await db_session.flush()
    assert (
        await service.regenerate_weekly_payments(league["season"].id, league["matchday"].id) == 0
    )
    assert await paid(db_session, league["matchday"].id) == before


async def test_payments_written_too_early_are_put_right_when_the_matchday_closes(
    db_session: AsyncSession, league: dict
) -> None:
    # What J6 of 2026-27 had: everyone charged the last one's amount, the
    # winner included, because the points were not all in yet.
    for part in league["parts"]:
        db_session.add(
            Transaction(
                season_id=league["season"].id,
                participant_id=part.id,
                matchday_id=league["matchday"].id,
                type="weekly_payment",
                amount=Decimal("2.00"),
            )
        )
    league["matchday"].stats_ok = True
    await db_session.flush()

    service = EconomyService(db_session)
    assert (
        await service.weekly_payments_need_redoing(league["season"].id, league["matchday"].id)
        is True
    )
    removed, written = await service.sync_weekly_payments(
        league["season"].id, league["matchday"].id
    )
    await db_session.flush()
    assert (removed, written) == (5, 2)
    assert await paid(db_session, league["matchday"].id) == {
        league["parts"][3].id: Decimal("1.00"),
        league["parts"][4].id: Decimal("2.00"),
    }


async def test_closing_again_moves_no_money(db_session: AsyncSession, league: dict) -> None:
    league["matchday"].stats_ok = True
    await db_session.flush()
    service = EconomyService(db_session)
    await service.generate_weekly_payments(league["season"].id, league["matchday"].id)
    await db_session.flush()

    assert (
        await service.weekly_payments_need_redoing(league["season"].id, league["matchday"].id)
        is False
    )
    assert await service.sync_weekly_payments(league["season"].id, league["matchday"].id) == (0, 0)


async def test_a_matchday_still_missing_stats_is_never_synced(
    db_session: AsyncSession, league: dict
) -> None:
    # J6 with its postponed match still to play: nothing is charged, and what
    # is already there is left for the close to put right.
    league["played"].stats_ok = False
    db_session.add(
        Transaction(
            season_id=league["season"].id,
            participant_id=league["parts"][0].id,
            matchday_id=league["matchday"].id,
            type="weekly_payment",
            amount=Decimal("2.00"),
        )
    )
    await db_session.flush()
    service = EconomyService(db_session)
    assert (
        await service.weekly_payments_need_redoing(league["season"].id, league["matchday"].id)
        is False
    )
    assert await service.sync_weekly_payments(league["season"].id, league["matchday"].id) == (0, 0)
    assert await paid(db_session, league["matchday"].id) == {
        league["parts"][0].id: Decimal("2.00")
    }
