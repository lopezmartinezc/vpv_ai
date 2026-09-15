"""A small league for the lineup chat: my squad of 15, a playoff rival who has
set a lineup, another participant who has not, and what the two sites say."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.auth.service import _create_token
from src.features.stats.schemas_advanced import PlayerPrediction
from src.shared.models.competition import Competition
from src.shared.models.competition_matchup import CompetitionMatchup
from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Match, Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player import Player
from src.shared.models.player_availability import PlayerAvailability, TeamNews
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import ScoringRule, Season, ValidFormation
from src.shared.models.team import Team
from src.shared.models.user import User

FORMATIONS = (
    ("1-3-4-3", 3, 4, 3),
    ("1-4-3-3", 4, 3, 3),
    ("1-4-4-2", 4, 4, 2),
    ("1-5-3-2", 5, 3, 2),
)

# name, position, team, xpts if he plays, starter % of recent matches
MY_SQUAD = (
    ("Joan Garcia", "POR", "Barcelona", 5.0, 100.0),
    ("Jokin Ezkieta", "POR", "Racing", 4.0, 100.0),
    ("Jules Kounde", "DEF", "Barcelona", 4.5, 100.0),
    ("Alejandro Balde", "DEF", "Barcelona", 4.0, 80.0),
    ("Pau Cubarsi", "DEF", "Barcelona", 3.8, 100.0),
    ("Jorge Mantilla", "DEF", "Racing", 3.0, 100.0),
    ("Florian Lejeune", "DEF", "Rayo Vallecano", 3.2, 100.0),
    ("Pedri", "MED", "Barcelona", 6.0, 100.0),
    ("Frenkie de Jong", "MED", "Barcelona", 7.0, 100.0),
    ("Isi Palazon", "MED", "Rayo Vallecano", 4.0, 90.0),
    ("Inigo Vicente", "MED", "Racing", 4.5, 100.0),
    ("Edu Exposito", "MED", "Espanyol", 3.5, 100.0),
    ("Raphinha", "DEL", "Barcelona", 7.0, 100.0),
    ("Javi Puado", "DEL", "Espanyol", 4.0, 60.0),
    ("Andres Martin", "DEL", "Racing", 3.0, 100.0),
)
RIVAL_SQUAD = (
    ("Dani Cardenas", "POR", "Rayo Vallecano"),
    ("Jorge de Frutos", "DEL", "Rayo Vallecano"),
)
OPPONENT = {
    "Barcelona": ("Racing", True),
    "Racing": ("Barcelona", False),
    "Rayo Vallecano": ("Espanyol", True),
    "Espanyol": ("Rayo Vallecano", False),
}


def prediction(player: Player, team: str, if_plays: float, starter: float) -> PlayerPrediction:
    xpts = round(if_plays * starter / 100, 1)
    opponent, home = OPPONENT[team]
    return PlayerPrediction(
        player_id=player.id,
        player_name=player.display_name,
        photo_path=None,
        position=player.position,
        team_name=team,
        opponent_name=opponent,
        is_home=home,
        season_avg=if_plays,
        form_5=None,
        location_avg=None,
        rival_factor=1.0,
        xpts=xpts,
        xpts_if_plays=if_plays,
        xpts_floor=xpts - 2,
        xpts_ceiling=xpts + 2,
        confidence="media",
        trend="stable",
        matchdays_played=5,
        starter_pct=starter,
        is_penalty_taker=player.display_name == "Raphinha",
    )


def token(user: User) -> dict[str, str]:
    assert user.session_id is not None
    return {"Authorization": f"Bearer {_create_token(user, user.session_id)}"}


async def person(db: AsyncSession, name: str, *, admin: bool = False) -> User:
    user = User(
        username=f"{name.lower()}{uuid.uuid4().hex[:6]}",
        display_name=name,
        password_hash="x",
        is_admin=admin,
        session_id=str(uuid.uuid4()),
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def league(db_session: AsyncSession) -> SimpleNamespace:
    db = db_session
    me = await person(db, "Carlos", admin=True)
    rival = await person(db, "Lucia")
    other = await person(db, "Marta")
    stranger = await person(db, "Nadie", admin=True)

    season = Season(
        name="2026-2027",
        status="active",
        matchday_start=6,
        matchday_end=38,
        lineup_deadline_min=30,
    )
    db.add(season)
    await db.flush()
    teams = {
        name: Team(season_id=season.id, name=name, slug=name.lower().replace(" ", "-"))
        for name in OPPONENT
    }
    db.add_all(teams.values())
    parts = {
        key: SeasonParticipant(season_id=season.id, user_id=user.id)
        for key, user in (("me", me), ("rival", rival), ("other", other))
    }
    db.add_all(parts.values())
    db.add_all(
        ValidFormation(formation=f, defenders=d, midfielders=m, forwards=w)
        for f, d, m, w in FORMATIONS
    )
    md5 = Matchday(season_id=season.id, number=5, status="finished")
    md6 = Matchday(
        season_id=season.id,
        number=6,
        status="pending",
        first_match_at=datetime(2026, 9, 20, 14, 15, tzinfo=UTC),
    )
    db.add_all([md5, md6])
    await db.flush()
    db.add_all(
        [
            Match(
                matchday_id=md6.id,
                home_team_id=teams["Barcelona"].id,
                away_team_id=teams["Racing"].id,
                played_at=datetime(2026, 9, 20, 14, 15, tzinfo=UTC),
            ),
            Match(
                matchday_id=md6.id,
                home_team_id=teams["Rayo Vallecano"].id,
                away_team_id=teams["Espanyol"].id,
                played_at=datetime(2026, 9, 21, 19, 0, tzinfo=UTC),
                counts=False,
            ),
        ]
    )

    def player(name: str, position: str, team: str, owner: SeasonParticipant) -> Player:
        p = Player(
            season_id=season.id,
            team_id=teams[team].id,
            name=name,
            display_name=name,
            slug=name.lower().replace(" ", "-"),
            position=position,
            owner_id=owner.id,
        )
        db.add(p)
        return p

    mine = {name: player(name, pos, team, parts["me"]) for name, pos, team, _, _ in MY_SQUAD}
    theirs = {name: player(name, pos, team, parts["rival"]) for name, pos, team in RIVAL_SQUAD}
    await db.flush()

    predictions = {
        mine[name].id: prediction(mine[name], team, if_plays, starter)
        for name, _, team, if_plays, starter in MY_SQUAD
    }

    def reading(
        team: str, source: str, raw: str, pct: int | None, **kw: object
    ) -> PlayerAvailability:
        return PlayerAvailability(
            season_id=season.id,
            matchday_number=6,
            source=source,
            team_id=teams[team].id,
            raw_name=raw,
            probability=pct,
            **kw,
        )

    db.add_all(
        [
            reading(
                "Barcelona",
                "futbolfantasy",
                "pedri-gonzalez",
                50,
                player_id=mine["Pedri"].id,
                starter=True,
                status="duda",
                note="Molestias en el pie",
            ),
            reading(
                "Barcelona",
                "futbolfantasy",
                "frenkie-de-jong",
                None,
                player_id=mine["Frenkie de Jong"].id,
                status="lesionado",
                note="Lesion de rodilla. Baja hasta octubre",
            ),
            reading(
                "Barcelona",
                "futbolfantasy",
                "raphinha",
                80,
                player_id=mine["Raphinha"].id,
                starter=True,
                previous_probability=60,
            ),
            reading(
                "Barcelona",
                "analiticafantasy",
                "Raphinha",
                70,
                player_id=mine["Raphinha"].id,
                starter=True,
            ),
            reading(
                "Rayo Vallecano",
                "analiticafantasy",
                "Batalla",
                0,
                status="lesionado",
                note="Fractura",
            ),
            TeamNews(
                season_id=season.id,
                team_id=teams["Barcelona"].id,
                source="futbolfantasy",
                title="Posibles alineaciones del Barcelona - Racing",
                url="https://www.futbolfantasy.com/laliga/noticias/151241-previa",
                published_at=datetime(2026, 9, 18, 9, 0, tzinfo=UTC),
            ),
            ScoringRule(
                season_id=season.id,
                rule_key="gol",
                position="DEL",
                value=Decimal("5"),
                description="Gol de delantero",
            ),
            PlayerStat(
                player_id=mine["Raphinha"].id,
                matchday_id=md5.id,
                position="DEL",
                played=True,
                minutes_played=90,
                pts_total=12,
                marca_rating="2",
                as_picas="3",
                goals=1,
            ),
        ]
    )
    competition = Competition(season_id=season.id, name="Playoff", type="playoff", status="active")
    db.add(competition)
    rival_lineup = Lineup(
        participant_id=parts["rival"].id,
        matchday_id=md6.id,
        formation="1-4-4-2",
        confirmed=True,
        confirmed_at=datetime(2026, 9, 19, 20, 0, tzinfo=UTC),
    )
    db.add(rival_lineup)
    await db.flush()
    db.add_all(
        [
            CompetitionMatchup(
                competition_id=competition.id,
                phase="regular",
                round_number=1,
                matchday_id=md6.id,
                participant_a_id=parts["me"].id,
                participant_b_id=parts["rival"].id,
            ),
            LineupPlayer(
                lineup_id=rival_lineup.id,
                player_id=theirs["Dani Cardenas"].id,
                position_slot="POR",
                display_order=1,
            ),
            LineupPlayer(
                lineup_id=rival_lineup.id,
                player_id=theirs["Jorge de Frutos"].id,
                position_slot="DEL",
                display_order=11,
            ),
        ]
    )
    await db.flush()
    return SimpleNamespace(
        season=season,
        me=me,
        rival=rival,
        other=other,
        stranger=stranger,
        parts=parts,
        mine=mine,
        predictions=predictions,
    )
