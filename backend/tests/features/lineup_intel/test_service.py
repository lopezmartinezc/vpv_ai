"""Refreshing the sources, keeping the change, and surviving a source down."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.features.lineup_intel import service as intel
from src.features.lineup_intel.service import (
    AF_BASE_URL,
    AF_MATCHDAY_URL,
    FF_TEAM_URL,
    P11_BASE_URL,
    P11_LINEUP_URL,
    P11_MATCH_URL,
    LineupIntelService,
    claim_manual_refresh,
    should_refresh,
)
from src.features.scraping.client import ScrapingError
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_availability import PlayerAvailability, TeamNews
from src.shared.models.season import Season
from src.shared.models.team import Team
from tests.features.lineup_intel.test_parsers import (
    BLOB,
    ESPANYOL_TOP,
    NOW,
    P11_KEY_JS,
    RAYO_TOP,
    af_page,
    ff_player,
    p11_lineup,
    p11_page,
)

MATCH = "/partido/100011989-rayo-vallecano-espanyol"
P11_SLUG = "22480-rayo-espanyol"
P11_SCRIPT = P11_BASE_URL + "/js/partido-show.js?id=bb"
P11_KEY = "1234567890-0123456789abcdef0123456789abcdef"


def p11_url(team: int, user: str, matchday: int = 6) -> str:
    return P11_LINEUP_URL.format(season=143, matchday=matchday, team=team, user=user, key=P11_KEY)


def ff_page(*players: str) -> str:
    return (
        '<div class="jugadores-titulares-1">'
        + "".join(players)
        + '</div><section class="news"><div class="noticias">'
        '<a href="https://www.futbolfantasy.com/laliga/noticias/1-previa">15/09 03:32 La previa</a>'
        "</div></section>"
    )


class FakeClient:
    pages: dict[str, str] = {}  # noqa: RUF012 — shared on purpose: set per test

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def fetch(self, url: str) -> str:
        if url not in self.pages:
            raise ScrapingError(url, RuntimeError("404"))
        return self.pages[url]


@pytest.fixture
async def league(db_session: AsyncSession) -> dict:
    season = Season(name="2026-2027", status="active", matchday_start=6, matchday_end=38)
    db_session.add(season)
    await db_session.flush()
    teams = {
        slug: Team(season_id=season.id, name=name, slug=slug)
        for name, slug in (
            ("Barcelona", "barcelona"),
            ("Rayo Vallecano", "rayo-vallecano"),
            ("Espanyol", "espanyol"),
        )
    }
    db_session.add_all(teams.values())
    await db_session.flush()

    def add(name: str, slug: str, team: str, position: str) -> Player:
        p = Player(
            season_id=season.id,
            team_id=teams[team].id,
            name=name,
            display_name=name,
            slug=slug,
            position=position,
        )
        db_session.add(p)
        return p

    players = {
        "raphinha": add("Raphinha", "raphinha", "barcelona", "DEL"),
        "pedri": add("Pedri", "pedri-gonzalez", "barcelona", "MED"),
        "audero": add("Emil Audero", "emil-audero", "rayo-vallecano", "POR"),
        "palazon": add("Isi Palazón", "isi-palazon", "rayo-vallecano", "DEL"),
        "de_frutos": add("Jorge de Frutos", "jorge-de-frutos", "espanyol", "DEL"),
    }
    matchday = Matchday(season_id=season.id, number=6)
    db_session.add(matchday)
    await db_session.flush()
    db_session.add(
        Match(
            matchday_id=matchday.id,
            home_team_id=teams["rayo-vallecano"].id,
            away_team_id=teams["espanyol"].id,
            source_url=f"https://www.futbolfantasy.com/partidos/{P11_SLUG}",
        )
    )
    await db_session.flush()
    FakeClient.pages = {
        FF_TEAM_URL.format(slug="barcelona"): ff_page(
            ff_player("raphinha", "60%"), ff_player("pedri-gonzalez", "50%", "duda_box_min.png")
        ),
        AF_MATCHDAY_URL.format(year=2026, matchday=6): f'<a href="{MATCH}">Ver partido</a>',
        AF_BASE_URL + MATCH: af_page(BLOB),
        # predicted11: the match page, its script with the visitor key, and the
        # elevens of each team's best predictors (the third Rayo one has none;
        # the fourth is not among the best three).
        P11_MATCH_URL.format(slug=P11_SLUG): p11_page(
            ("Rayo Vallecano", 14, [*RAYO_TOP, ("cuarto", 40, "70")]),
            ("Espanyol", 5, ESPANYOL_TOP),
        ),
        P11_SCRIPT: P11_KEY_JS,
        p11_url(14, "watusi74"): p11_lineup(
            "watusi74", ("Emil Audero", "Portero"), ("Isi Palazón", "Delantero")
        ),
        p11_url(14, "PilaAlcalinaAAA"): p11_lineup(
            "PilaAlcalinaAAA", ("Emil Audero", "Portero"), ("Augusto Batalla", "Portero")
        ),
        p11_url(14, "Aroodii"): p11_lineup("Aroodii"),
        p11_url(14, "cuarto"): p11_lineup("cuarto", ("Isi Palazón", "Delantero")),
        p11_url(5, "huugo_21"): p11_lineup("huugo_21", ("Jorge de Frutos", "Delantero")),
    }
    intel._last_manual_refresh.clear()
    return {"season": season, "teams": teams, "players": players}


async def rows(db: AsyncSession, source: str | None = None) -> list[PlayerAvailability]:
    query = select(PlayerAvailability)
    if source:
        query = query.where(PlayerAvailability.source == source)
    return list((await db.execute(query)).scalars())


def service(db: AsyncSession) -> LineupIntelService:
    return LineupIntelService(db, client_factory=FakeClient)


async def test_both_sources_are_read_and_matched(db_session: AsyncSession, league: dict) -> None:
    result = await service(db_session).refresh(league["season"].id, 6, now=NOW)
    ff = {r.raw_name: r for r in await rows(db_session, "futbolfantasy")}
    assert ff["raphinha"].player_id == league["players"]["raphinha"].id
    assert (ff["pedri-gonzalez"].probability, ff["pedri-gonzalez"].status) == (50, "duda")
    af = {r.raw_name: r for r in await rows(db_session, "analiticafantasy")}
    assert af["Emil Audero"].player_id == league["players"]["audero"].id
    assert af["Isi Palazón"].player_id == league["players"]["palazon"].id
    assert af["De Frutos"].player_id == league["players"]["de_frutos"].id
    # Not in our squad: kept, but pinned on nobody.
    assert af["Batalla"].player_id is None
    assert result["futbolfantasy"].news == 1


async def test_a_change_keeps_the_previous_probability(
    db_session: AsyncSession, league: dict
) -> None:
    await service(db_session).refresh(league["season"].id, 6, now=NOW)
    FakeClient.pages[FF_TEAM_URL.format(slug="barcelona")] = ff_page(
        ff_player("raphinha", "80%"), ff_player("pedri-gonzalez", "50%")
    )
    await service(db_session).refresh(league["season"].id, 6, now=NOW)
    await service(db_session).refresh(league["season"].id, 6, now=NOW)
    ff = {r.raw_name: r for r in await rows(db_session, "futbolfantasy")}
    await db_session.refresh(ff["raphinha"])
    await db_session.refresh(ff["pedri-gonzalez"])
    assert (ff["raphinha"].probability, ff["raphinha"].previous_probability) == (80, 60)
    assert (ff["pedri-gonzalez"].probability, ff["pedri-gonzalez"].previous_probability) == (
        50,
        None,
    )


async def test_a_name_no_longer_listed_goes_but_a_failed_page_keeps_the_last_reading(
    db_session: AsyncSession, league: dict
) -> None:
    await service(db_session).refresh(league["season"].id, 6, now=NOW)
    FakeClient.pages[FF_TEAM_URL.format(slug="barcelona")] = ff_page(ff_player("raphinha", "60%"))
    await service(db_session).refresh(league["season"].id, 6, now=NOW)
    assert {r.raw_name for r in await rows(db_session, "futbolfantasy")} == {"raphinha"}

    del FakeClient.pages[FF_TEAM_URL.format(slug="barcelona")]
    await service(db_session).refresh(league["season"].id, 6, now=NOW)
    assert {r.raw_name for r in await rows(db_session, "futbolfantasy")} == {"raphinha"}


async def test_one_source_down_does_not_take_the_other(
    db_session: AsyncSession, league: dict
) -> None:
    del FakeClient.pages[AF_MATCHDAY_URL.format(year=2026, matchday=6)]
    result = await service(db_session).refresh(league["season"].id, 6, now=NOW)
    assert result["analiticafantasy"].errors
    assert await rows(db_session, "futbolfantasy")
    assert not await rows(db_session, "analiticafantasy")


async def test_a_source_can_be_switched_off(
    db_session: AsyncSession, league: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "lineup_intel_sources", "futbolfantasy")
    result = await service(db_session).refresh(league["season"].id, 6, now=NOW)
    assert set(result) == {"futbolfantasy"}
    assert not await rows(db_session, "analiticafantasy")


async def test_reading_groups_each_player_and_lists_the_unmatched(
    db_session: AsyncSession, league: dict
) -> None:
    await service(db_session).refresh(league["season"].id, 6, now=NOW)
    view = await service(db_session).read(league["season"].id, 6)
    raphinha = next(p for p in view.players if p.player_id == league["players"]["raphinha"].id)
    assert [r.source for r in raphinha.readings] == ["futbolfantasy"]
    assert "Batalla" in {u.raw_name for u in view.unmatched}
    assert [n.title for n in view.news] == ["La previa"]
    assert view.updated_at is not None
    assert (await db_session.execute(select(TeamNews))).scalars().first() is not None


async def test_a_futbolfantasy_player_without_a_page_is_matched_by_name(
    db_session: AsyncSession, league: dict
) -> None:
    FakeClient.pages[FF_TEAM_URL.format(slug="barcelona")] = ff_page(
        ff_player("", "70%", name="Pedri")
    )
    await service(db_session).refresh(league["season"].id, 6, now=NOW)
    ff = {r.raw_name: r for r in await rows(db_session, "futbolfantasy")}
    assert ff["Pedri"].player_id == league["players"]["pedri"].id


def test_the_scheduled_refresh_acts_only_in_the_last_48_hours() -> None:
    deadline = datetime(2026, 9, 20, 18, 30, tzinfo=UTC)
    assert should_refresh(deadline, deadline - timedelta(hours=47)) is True
    assert should_refresh(deadline, deadline - timedelta(hours=49)) is False
    assert should_refresh(deadline, deadline + timedelta(minutes=1)) is False
    assert should_refresh(None, deadline) is False


def test_a_manual_refresh_waits_ten_minutes() -> None:
    intel._last_manual_refresh.clear()
    claim_manual_refresh(1, 6, NOW)
    with pytest.raises(BusinessRuleError):
        claim_manual_refresh(1, 6, NOW + timedelta(minutes=9))
    claim_manual_refresh(1, 6, NOW + timedelta(minutes=10))
    claim_manual_refresh(1, 7, NOW)


async def test_each_top_predictor_of_predicted11_is_a_source_of_his_own(
    db_session: AsyncSession, league: dict
) -> None:
    season = league["season"].id
    result = await service(db_session).refresh(season, 6, now=NOW)
    assert result["predicted11"].errors == []
    rayo = league["teams"]["rayo-vallecano"].id
    first = {r.raw_name: r for r in await rows(db_session, "predicted11_1") if r.team_id == rayo}
    palazon = first["Isi Palazón"]
    assert palazon.player_id == league["players"]["palazon"].id
    assert (palazon.probability, palazon.starter) == (100, True)
    assert palazon.note == "watusi74, 1.º del destacado del Rayo Vallecano (83,6 % de acierto)"
    second = {r.raw_name: r for r in await rows(db_session, "predicted11_2")}
    assert set(second) == {"Emil Audero", "Augusto Batalla"}
    assert second["Augusto Batalla"].player_id is None
    # No eleven from the third: he does not count, not even as a 0. The
    # fourth is not read at all.
    assert not await rows(db_session, "predicted11_3")
    assert not await rows(db_session, "predicted11_4")

    view = await service(db_session).read(season, 6)
    assert {(c.source, c.team_name) for c in view.coverage} == {
        ("predicted11_1", "Rayo Vallecano"),
        ("predicted11_2", "Rayo Vallecano"),
        ("predicted11_1", "Espanyol"),
    }
    readings = next(
        p.readings for p in view.players if p.player_id == league["players"]["palazon"].id
    )
    assert [r.source for r in readings] == ["analiticafantasy", "predicted11_1"]


async def test_predicted11_is_read_every_six_hours_unless_asked(
    db_session: AsyncSession, league: dict
) -> None:
    season = league["season"].id
    now = datetime.now(UTC)
    assert "predicted11" in await service(db_session).refresh(season, 6, now=now)
    soon = now + timedelta(hours=1)
    assert "predicted11" not in await service(db_session).refresh(season, 6, now=soon)
    asked = await service(db_session).refresh(season, 6, now=soon, force_p11=True)
    assert "predicted11" in asked
    later = now + timedelta(hours=7)
    assert "predicted11" in await service(db_session).refresh(season, 6, now=later)


async def test_predicted11_down_or_on_another_matchday_leaves_the_rest(
    db_session: AsyncSession, league: dict
) -> None:
    season = league["season"].id
    del FakeClient.pages[P11_SCRIPT]
    result = await service(db_session).refresh(season, 6, now=NOW)
    assert result["predicted11"].errors
    assert await rows(db_session, "futbolfantasy")
    assert await rows(db_session, "analiticafantasy")
    assert not await rows(db_session, "predicted11_1")

    # Its page is already on another matchday: nothing is read from it.
    FakeClient.pages[P11_SCRIPT] = P11_KEY_JS
    FakeClient.pages[P11_MATCH_URL.format(slug=P11_SLUG)] = p11_page(
        ("Rayo Vallecano", 14, RAYO_TOP), ("Espanyol", 5, ESPANYOL_TOP), matchday=7
    )
    result = await service(db_session).refresh(season, 6, now=NOW, force_p11=True)
    assert any("J7" in e for e in result["predicted11"].errors)
    assert not await rows(db_session, "predicted11_1")
