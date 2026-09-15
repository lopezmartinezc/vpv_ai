"""analiticafantasy's team and player names find ours, and doubtful ones do not."""

from __future__ import annotations

from src.features.lineup_intel.matching import RosterPlayer, TeamRef, match_player, match_team
from src.features.lineup_intel.parsers import SourcePlayer

OURS = [
    ("Alavés", "alaves"),
    ("Athletic", "athletic"),
    ("Atlético", "atletico"),
    ("Barcelona", "barcelona"),
    ("Betis", "betis"),
    ("Celta", "celta"),
    ("Deportivo", "deportivo"),
    ("Elche", "elche"),
    ("Espanyol", "espanyol"),
    ("Getafe", "getafe"),
    ("Levante", "levante"),
    ("Málaga", "malaga"),
    ("Osasuna", "osasuna"),
    ("Racing", "racing"),
    ("Rayo Vallecano", "rayo-vallecano"),
    ("Real Madrid", "real-madrid"),
    ("Real Sociedad", "real-sociedad"),
    ("Sevilla", "sevilla"),
    ("Valencia", "valencia"),
    ("Villarreal", "villarreal"),
]
TEAMS = [TeamRef(id=i, name=name, slug=slug) for i, (name, slug) in enumerate(OURS, start=1)]

# As analiticafantasy writes them (J6-J7 2026-27), in the same order as OURS.
THEIRS = [
    "Alaves",
    "Athletic Club",
    "Atletico Madrid",
    "Barcelona",
    "Real Betis",
    "Celta Vigo",
    "Deportivo La Coruna",
    "Elche",
    "Espanyol",
    "Getafe",
    "Levante",
    "Malaga",
    "Osasuna",
    "Racing Santander",
    "Rayo Vallecano",
    "Real Madrid",
    "Real Sociedad",
    "Sevilla",
    "Valencia",
    "Villarreal",
]


def test_every_analiticafantasy_team_finds_ours() -> None:
    assert [match_team(name, TEAMS) for name in THEIRS] == [t.id for t in TEAMS]


def test_atletico_madrid_is_not_real_madrid() -> None:
    assert match_team("Atletico Madrid", TEAMS) == 3


def test_an_unknown_team_stays_unmatched() -> None:
    assert match_team("Manchester United", TEAMS) is None


def test_a_name_two_teams_share_stays_unmatched() -> None:
    racings = [
        TeamRef(1, "Racing Santander", "racing"),
        TeamRef(2, "Racing Ferrol", "racing-ferrol"),
    ]
    assert match_team("Racing", racings) is None
    assert match_team("Racing Santander", racings) == 1


ROSTER = [
    RosterPlayer(1, 10, "Marko Dmitrović", "marko-dmitrovic", "POR"),
    RosterPlayer(2, 10, "Joan Garcia", "joan-garcia", "POR"),
    RosterPlayer(3, 10, "Eric Garcia", "eric-garcia", "DEF"),
    RosterPlayer(4, 10, "Kaku", "kaku", "MED", aliases="Alejandro Romero Gamarra"),
    RosterPlayer(5, 10, "Adrià Pedrosa", "adria-pedrosa", "DEF"),
]


def player(name: str, slug: str | None = None, position: str | None = None) -> SourcePlayer:
    return SourcePlayer(name=name, probability=70, starter=True, slug=slug, position=position)


def test_a_surname_finds_the_player_accents_and_slug_ids_aside() -> None:
    assert match_player(player("Dmitrovic", "m-dmitrovic-2813"), ROSTER) == 1
    assert match_player(player("Pedrosa", "adria-pedrosa-47329"), ROSTER) == 5


def test_a_full_name_beats_a_shared_surname() -> None:
    assert match_player(player("Joan Garcia"), ROSTER) == 2


def test_a_shared_surname_alone_stays_unmatched_unless_the_position_settles_it() -> None:
    assert match_player(player("Garcia"), ROSTER) is None
    assert match_player(player("Garcia", position="DEF"), ROSTER) == 3


def test_an_alias_bridges_a_nickname() -> None:
    assert match_player(player("Gamarra"), ROSTER) == 4


def test_a_stranger_stays_unmatched() -> None:
    assert match_player(player("Nadie Conocido"), ROSTER) is None


def test_a_particle_like_de_is_no_match() -> None:
    roster = [RosterPlayer(6, 10, "Frenkie de Jong", "frenkie-de-jong", "MED")]
    assert match_player(player("Luis de la Fuente"), roster) is None
