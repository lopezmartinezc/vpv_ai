"""A live goal alert says when the goal is a 🍔.

A 🍔 is a goal by a player whose owner left him out of that matchday's eleven —
the burger ranking's rule (``burger_ranking/service.py``). The ranking counted it
after the fact; the live alert now says so as it happens: "⚽🍔 GOL" and
"🍔 no estaba en su once" next to the owner.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.scraping import live_monitor
from src.features.scraping.live_events import LiveEvent
from src.features.scraping.live_monitor import BURGER, format_live_alert, is_burger_goal
from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.user import User

OWNER, SCORER = 7, 70


def owned(owner_id: int | None = OWNER) -> Player:
    return Player(id=SCORER, owner_id=owner_id)


# --- the rule ------------------------------------------------------------------


def test_a_goal_by_a_player_his_owner_left_out_is_a_burger() -> None:
    assert is_burger_goal("goal", owned(), True, True, lined_up=set()) is True


def test_a_goal_by_a_fielded_player_is_not() -> None:
    assert is_burger_goal("goal", owned(), True, True, lined_up={(OWNER, SCORER)}) is False


def test_being_in_someone_elses_eleven_does_not_count() -> None:
    assert is_burger_goal("goal", owned(), True, True, lined_up={(OWNER + 1, SCORER)}) is True


def test_a_player_nobody_owns_is_never_a_burger() -> None:
    assert is_burger_goal("goal", owned(None), True, True, lined_up=set()) is False
    assert is_burger_goal("goal", None, True, True, lined_up=set()) is False


def test_only_goals_are_burgers() -> None:
    assert is_burger_goal("assist", owned(), True, True, lined_up=set()) is False


def test_not_when_the_matchday_or_the_fixture_does_not_count() -> None:
    """Pre-season jornadas and postponed fixtures are left out of the ranking too."""
    assert is_burger_goal("goal", owned(), False, True, lined_up=set()) is False
    assert is_burger_goal("goal", owned(), True, False, lined_up=set()) is False


# --- the message ---------------------------------------------------------------


def event(name: str = "Suplente", kind: str = "goal") -> LiveEvent:
    return LiveEvent(minute="23'", event_type=kind, player_name=name, player_slug="x", raw_text="")


def message(**kw: object) -> str:
    defaults: dict = {
        "home_team": "Local",
        "away_team": "Visitante",
        "score": "1-0",
        "matchday_number": 6,
        "owner_name": "Ana",
    }
    defaults.update(kw)
    ev = defaults.pop("event", event())
    return format_live_alert(ev, **defaults)


def test_a_burger_goal_carries_the_icon_and_says_why() -> None:
    text = message(burger=True)
    assert text.startswith(f"⚽{BURGER} <b>GOL</b>")
    assert f"Propietario: Ana — {BURGER} no estaba en su once" in text


def test_any_other_goal_carries_no_burger() -> None:
    text = message()
    assert BURGER not in text
    assert text == "⚽ <b>GOL</b> — Suplente (23')\nLocal 1-0 Visitante | J6\nPropietario: Ana"


def test_a_goal_by_nobody_s_player_has_no_owner_line() -> None:
    assert "Propietario" not in message(owner_name=None)


def test_names_are_escaped_for_telegram_html() -> None:
    text = message(event=event("<b>X</b>"), owner_name="A & B")
    assert "&lt;b&gt;X&lt;/b&gt;" in text and "A &amp; B" in text


# --- end to end: a live match with two goals --------------------------------------


def goal_comment(minute: str, slug: str, name: str) -> str:
    return (
        f'<div class="comentario"><span class="minutos">{minute}</span>'
        f'<img src="https://static.futbolfantasy.com/img/balon.png"/>'
        f'<a class="player" href="https://www.futbolfantasy.com/jugadores/{slug}">{name}</a>'
        f"</div>"
    )


class _FakeClient:
    html = ""

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def fetch(self, url: str) -> str:
        return self.html


@pytest.fixture
async def live_match(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """J6 in play. Ana fielded Titular and left Suplente out; both score."""
    season = Season(name="2026-2027", status="active", matchday_start=6, matchday_end=38)
    db_session.add(season)
    await db_session.flush()
    user = User(username="ana_live", display_name="Ana", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ana = SeasonParticipant(season_id=season.id, user_id=user.id)
    db_session.add(ana)
    home, away = (
        Team(season_id=season.id, name="Local", slug="local"),
        Team(season_id=season.id, name="Visitante", slug="visitante"),
    )
    db_session.add_all([home, away])
    await db_session.flush()
    jornada = Matchday(season_id=season.id, number=6, counts=True)
    db_session.add(jornada)
    await db_session.flush()
    match = Match(
        matchday_id=jornada.id,
        home_team_id=home.id,
        away_team_id=away.id,
        counts=True,
        source_url="https://www.futbolfantasy.com/partidos/local-visitante",
        played_at=datetime.now(UTC) - timedelta(minutes=30),
        home_score=2,
        away_score=0,
    )
    db_session.add(match)

    def player(name: str) -> Player:
        return Player(
            season_id=season.id,
            team_id=home.id,
            name=name,
            display_name=name,
            slug=name.lower(),
            position="DEL",
            owner_id=ana.id,
        )

    titular, suplente = player("Titular"), player("Suplente")
    db_session.add_all([titular, suplente])
    await db_session.flush()
    lineup = Lineup(participant_id=ana.id, matchday_id=jornada.id, formation="1-4-3-3")
    db_session.add(lineup)
    await db_session.flush()
    db_session.add(
        LineupPlayer(
            lineup_id=lineup.id, player_id=titular.id, position_slot="DEL", display_order=1
        )
    )
    await db_session.flush()

    _FakeClient.html = goal_comment("23'", "suplente", "Suplente") + goal_comment(
        "41'", "titular", "Titular"
    )
    sent: list[str] = []

    async def fake_send(session: AsyncSession, text: str, season_id: int | None = None) -> bool:
        sent.append(text)
        return True

    monkeypatch.setattr(live_monitor, "ScrapingClient", _FakeClient)
    monkeypatch.setattr(live_monitor, "_send_telegram", fake_send)
    # Past the first scan, which only marks what is already there as seen.
    live_monitor._sent_events.clear()
    live_monitor._sent_events[match.id] = set()
    yield sent
    live_monitor._sent_events.clear()


async def test_the_live_alert_marks_the_burger_and_only_it(
    db_session: AsyncSession, live_match: list[str]
) -> None:
    await live_monitor._check_live_matches(db_session)
    by_player = {("Suplente" if "Suplente" in m else "Titular"): m for m in live_match}
    assert set(by_player) == {"Suplente", "Titular"}
    assert BURGER in by_player["Suplente"]
    assert "no estaba en su once" in by_player["Suplente"]
    assert BURGER not in by_player["Titular"]
