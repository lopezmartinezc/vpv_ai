"""A whole Apertura through the engine: calendar, table, KO and the final."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError
from src.features.competitions.service import CompetitionService
from src.shared.models.competition_matchup import CompetitionMatchup
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.season import Season
from src.shared.models.user import User

KO = [17, 18, 19, 20, 21]


@pytest.fixture
async def liga(db_session: AsyncSession) -> SimpleNamespace:
    db = db_session
    season = Season(name="2026-2027", status="active", matchday_start=6, matchday_end=38)
    db.add(season)
    await db.flush()
    users = [
        User(username=f"p{i}{uuid.uuid4().hex[:6]}", display_name=f"P{i + 1}", password_hash="x")
        for i in range(11)
    ]
    db.add_all(users)
    await db.flush()
    parts = [
        SeasonParticipant(season_id=season.id, user_id=u.id, draft_order=i + 1)
        for i, u in enumerate(users)
    ]
    db.add_all(parts)
    mds = {n: Matchday(season_id=season.id, number=n, status="pending") for n in range(6, 22)}
    db.add_all(mds.values())
    await db.flush()
    return SimpleNamespace(
        db=db,
        season=season,
        p=[p.id for p in parts],  # p[0] is P1, the strongest by default
        mds=mds,
        service=CompetitionService(db),
    )


def strength(liga: SimpleNamespace) -> dict[int, int]:
    """P1 outscores P2, who outscores P3, and so on."""
    return {pid: 100 - 5 * i for i, pid in enumerate(liga.p)}


async def score(liga: SimpleNamespace, number: int, points: dict[int, int]) -> None:
    md = liga.mds[number]
    liga.db.add_all(
        ParticipantMatchdayScore(participant_id=pid, matchday_id=md.id, total_points=pts)
        for pid, pts in points.items()
    )
    await liga.db.flush()
    await liga.service.recalculate_matchups_for_matchday(md.id)


async def create(liga: SimpleNamespace) -> int:
    comp = await liga.service.create_playoff(liga.season.id, "liga_berger_ko8_bo3", "Apertura")
    await liga.service.start_regular_phase(comp.id, 6, 16, planned_ko_matchday_numbers=KO)
    return comp.id


async def matchups(liga: SimpleNamespace, number: int) -> list[CompetitionMatchup]:
    result = await liga.db.execute(
        select(CompetitionMatchup)
        .where(CompetitionMatchup.matchday_id == liga.mds[number].id)
        .order_by(CompetitionMatchup.id)
    )
    return list(result.scalars())


async def play_to_the_final(liga: SimpleNamespace) -> int:
    comp_id = await create(liga)
    for n in range(6, 19):
        await score(liga, n, strength(liga))
    return comp_id


async def test_a_jornada_already_scored_is_settled_when_the_calendar_is_made(
    liga: SimpleNamespace,
) -> None:
    await score(liga, 6, strength(liga))  # J6 closed before the playoff existed
    await create(liga)
    j6 = await matchups(liga, 6)
    assert len(j6) == 5
    assert all(m.score_a is not None and m.winner_participant_id is not None for m in j6)


async def test_the_apertura_runs_from_the_calendar_to_the_champion(liga: SimpleNamespace) -> None:
    comp_id = await create(liga)
    regular = [m for n in range(6, 17) for m in await matchups(liga, n)]
    assert len(regular) == 55

    for n in range(6, 17):
        await score(liga, n, strength(liga))
    table = (await liga.service.get_standings(comp_id)).groups[0].entries
    assert [e.participant_id for e in table] == liga.p
    assert [e.rank for e in table] == list(range(1, 12))

    # The KO started by itself after the last regular jornada.
    seed = {pid: i + 1 for i, pid in enumerate(liga.p)}
    quarters = await matchups(liga, 17)
    assert [(seed[m.participant_a_id], seed[m.participant_b_id]) for m in quarters] == [
        (1, 8),
        (4, 5),
        (2, 7),
        (3, 6),
    ]
    # A drawn cuartos goes to the better seed: P4 and P5 level.
    j17 = strength(liga) | {liga.p[3]: 70, liga.p[4]: 70}
    await score(liga, 17, j17)
    semis = await matchups(liga, 18)
    assert [(seed[m.participant_a_id], seed[m.participant_b_id]) for m in semis] == [
        (1, 4),
        (2, 3),
    ]

    await score(liga, 18, strength(liga))
    finals = await matchups(liga, 19) + await matchups(liga, 20) + await matchups(liga, 21)
    assert [(m.participant_a_id, m.participant_b_id) for m in finals] == [
        (liga.p[0], liga.p[1])
    ] * 3

    await score(liga, 19, strength(liga))
    assert (await liga.service.get_matchups(comp_id)).competition.status == "ko"
    await score(liga, 20, strength(liga))
    view = await liga.service.get_matchups(comp_id)
    assert view.competition.status == "completed"
    series = view.final_series
    assert series is not None
    assert (series.wins_a, series.wins_b, series.winner_participant_id) == (2, 0, liga.p[0])
    assert [leg.result for leg in series.legs] == ["a", "a", "not_needed"]
    assert series.winner_name == "P1"


async def test_a_drawn_final_jornada_waits_for_the_third_and_the_difference(
    liga: SimpleNamespace,
) -> None:
    comp_id = await play_to_the_final(liga)
    p1, p2 = liga.p[0], liga.p[1]

    await score(liga, 19, {p1: 60, p2: 50})  # P1 +10
    await score(liga, 20, {p1: 45, p2: 45})  # level
    view = await liga.service.get_matchups(comp_id)
    assert view.competition.status == "ko"
    assert [leg.result for leg in view.final_series.legs] == ["a", "pending", "pending"]  # type: ignore[union-attr]
    # The drawn jornada is not handed to the better seed on its own.
    assert (await matchups(liga, 20))[0].winner_participant_id is None

    await score(liga, 21, {p1: 50, p2: 70})  # P2 +20: the draw goes to P2 on difference
    view = await liga.service.get_matchups(comp_id)
    series = view.final_series
    assert series is not None
    assert (series.wins_a, series.wins_b, series.winner_participant_id) == (1, 2, p2)
    assert (series.legs[1].result, series.legs[1].decided_by) == ("b", "difference")
    assert view.competition.status == "completed"


async def test_the_formats_count_the_seasons_own_participants(
    client: AsyncClient, liga: SimpleNamespace
) -> None:
    by_id = {
        f["format_id"]: f
        for f in (await client.get(f"/api/competitions/formats?season_id={liga.season.id}")).json()
    }
    assert (
        by_id["liga_berger_ko8_bo3"]["n_rounds_regular"],
        by_id["liga_berger_ko8_bo3"]["n_rounds_ko"],
    ) == (11, 5)
    # Without a season, the old probe of 13 participants.
    probe = {f["format_id"]: f for f in (await client.get("/api/competitions/formats")).json()}
    assert probe["liga_berger_ko8_bo3"]["n_rounds_regular"] == 13


async def test_the_final_series_is_absent_before_the_final_and_for_other_formats(
    liga: SimpleNamespace,
) -> None:
    comp_id = await create(liga)
    assert (await liga.service.get_matchups(comp_id)).final_series is None
    old = await liga.service.create_playoff(liga.season.id, "liga_berger_ko8", "Otro")
    assert (await liga.service.get_matchups(old.id)).final_series is None


async def standings_for(db: AsyncSession, liga: SimpleNamespace, format_id: str, cruces) -> list:  # type: ignore[no-untyped-def]
    """A table built from hand-made regular cruces: (a, b, score_a, score_b)."""
    service = CompetitionService(db)
    comp = await service.create_playoff(liga.season.id, format_id, f"Tabla {format_id}")
    for i, (a, b, sa, sb) in enumerate(cruces, start=1):
        db.add(
            CompetitionMatchup(
                competition_id=comp.id,
                phase="regular",
                group_label="overall",
                round_number=i,
                participant_a_id=a,
                participant_b_id=b,
                score_a=sa,
                score_b=sb,
                winner_participant_id=a if sa > sb else b if sb > sa else None,
            )
        )
    await db.flush()
    return (await service.get_standings(comp.id)).groups[0].entries


async def test_level_on_points_the_head_to_head_comes_before_the_difference(
    db_session: AsyncSession, liga: SimpleNamespace
) -> None:
    v, x, y, w = liga.p[:4]
    # X and Y end on 3 points. X beat Y, but Y has the far better difference.
    cruces = [(x, y, 11, 10), (y, w, 30, 10), (v, x, 12, 10), (v, w, 10, 10)]
    rows = await standings_for(db_session, liga, "liga_berger_ko8_bo3", cruces)
    assert [(e.participant_id, e.rank) for e in rows] == [(v, 1), (x, 2), (y, 3), (w, 4)]

    # The Mundial rule has no head to head: the difference puts Y ahead.
    old = await standings_for(db_session, liga, "liga_berger_ko8", cruces)
    assert [(e.participant_id, e.rank) for e in old] == [(v, 1), (y, 2), (x, 3), (w, 4)]


async def test_a_drawn_head_to_head_goes_to_the_difference(
    db_session: AsyncSession, liga: SimpleNamespace
) -> None:
    x, y, v, w = liga.p[:4]
    # X and Y drew their cruce and both end on 4 points: X +5, Y +2.
    cruces = [(x, y, 10, 10), (x, w, 15, 10), (y, v, 12, 10)]
    rows = await standings_for(db_session, liga, "liga_berger_ko8_bo3", cruces)
    assert [(e.participant_id, e.rank) for e in rows] == [(x, 1), (y, 2), (v, 3), (w, 4)]


async def test_three_in_a_circle_are_split_by_the_difference(
    db_session: AsyncSession, liga: SimpleNamespace
) -> None:
    x, y, z = liga.p[:3]
    # Each beat one and lost to one: the mini-table is level, so the
    # difference decides. X +4, Z -1, Y -3.
    cruces = [(x, y, 15, 10), (y, z, 12, 10), (z, x, 11, 10)]
    rows = await standings_for(db_session, liga, "liga_berger_ko8_bo3", cruces)
    assert [(e.participant_id, e.rank) for e in rows] == [(x, 1), (z, 2), (y, 3)]


async def test_a_circle_of_three_stays_level(
    db_session: AsyncSession, liga: SimpleNamespace
) -> None:
    x, y, z = liga.p[:3]
    cruces = [(x, y, 15, 10), (y, z, 15, 10), (z, x, 15, 10)]
    rows = await standings_for(db_session, liga, "liga_berger_ko8_bo3", cruces)
    assert {e.rank for e in rows} == {1}


async def test_the_mini_table_counts_a_win_over_two_draws(
    db_session: AsyncSession, liga: SimpleNamespace
) -> None:
    a, b, c, o1, o2 = liga.p[:5]
    # A, B and C end on 4 points. Among themselves A beat B and both drew
    # with C: A 4, C 2, B 1 — so A goes first despite the worst difference
    # (-9, against 0 for B and C).
    cruces = [
        (a, b, 11, 10),
        (a, c, 10, 10),
        (o2, a, 20, 10),
        (b, c, 10, 10),
        (b, o1, 11, 10),
        (c, o1, 10, 10),
        (c, o2, 10, 10),
        (o2, o1, 11, 10),
    ]
    rows = await standings_for(db_session, liga, "liga_berger_ko8_bo3", cruces)
    assert [(e.participant_id, e.rank) for e in rows] == [(o2, 1), (a, 2), (c, 3), (b, 4), (o1, 5)]


async def test_a_format_that_refuses_is_a_business_error_not_a_crash(
    liga: SimpleNamespace,
) -> None:
    # balanced_ko4 is for 13 participants; this season has 11.
    mundial = await liga.service.create_playoff(liga.season.id, "balanced_ko4", "Mundial")
    with pytest.raises(BusinessRuleError, match="13 participants"):
        await liga.service.start_regular_phase(mundial.id, 6, 11)

    # Every cruce drawn: all eleven level on everything, so no clean cut.
    apertura = await liga.service.create_playoff(liga.season.id, "liga_berger_ko8_bo3", "Apertura")
    await liga.service.start_regular_phase(apertura.id, 6, 16)
    for n in range(6, 17):
        await score(liga, n, dict.fromkeys(liga.p, 50))
    with pytest.raises(BusinessRuleError, match="Empate sin desempate"):
        await liga.service.start_ko_phase(apertura.id, KO)
