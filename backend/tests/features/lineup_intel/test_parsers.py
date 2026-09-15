"""The parsers read what the sites actually publish, and nothing breaks
when a page changes shape.

The HTML here is written by hand to mirror the structure verified on
15/09/2026; no page of theirs is copied into this public repository.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from src.features.lineup_intel.parsers import (
    MADRID,
    parse_af_match,
    parse_af_matchday_links,
    parse_ff_team,
    parse_p11_guest_key,
    parse_p11_lineup,
    parse_p11_match,
    parse_p11_script_path,
)

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
ICONS = "https://static.futbolfantasy.com/uploads/images"
FF = "https://www.futbolfantasy.com/jugadores"
# What the shirt's label carries after the name, as on the real page.
LABEL_TAIL = (
    "7 7 5 -2 4 23,37M (+1,22M) 4,22M (+260k) 19 años Izquierdo 5 partidos 258 min. Rotación"
)


def ff_player(
    slug: str, pct: str, *icons: str, unavailable: str = "0", name: str | None = None
) -> str:
    """A shirt on the pitch. No slug: a player without his own page (href="#")."""
    imgs = "".join(f'<img src="{ICONS}/{icon}">' for icon in icons)
    href = f"{FF}/{slug}" if slug else "#"
    return (
        '<div class="jugador_1 tipo_campo campo camiseta-wrapper">'
        f'<a class="camiseta" href="{href}" data-probabilidad="{pct}" '
        f'data-nodisponible="{unavailable}">{imgs}</a>'
        f'<div class="juggadores"><a class="juggador pos-0" href="{href}">{name or slug} {LABEL_TAIL}</a>'
        '<a class="juggador pos-1" href="#">Alternativa Otra 3</a></div>'
        "</div>"
    )


def ff_absence(slug: str, name: str, icon: str, *lines: str) -> str:
    """A row of "Estado físico de la plantilla"."""
    return (
        '<div class="elemento lesionado">'
        f'<div class="fotocontainer"><a href="{FF}/{slug}"><img src="{ICONS}/camisetas/x.png"></a></div>'
        f'<div class="icono"><img alt="Estado" src="{ICONS}/{icon}"></div>'
        f'<div class="nombre"><a href="{FF}/{slug}">{name}</a></div>'
        + "".join(f"<div>{line}</div>" for line in lines)
        + '<a href="https://www.futbolfantasy.com/laliga/noticias/1-parte">Parte médico</a>'
        "</div>"
    )


FF_PAGE = (
    "<html><body>"
    '<div class="jugadores-titulares-22477 mod lesionados mb-0">'
    + ff_player("raphinha", "60%", "rotacion.png")
    + ff_player("pedri-gonzalez", "50%", "duda_box_min.png")
    + ff_player("jules-kounde", "80%")
    + ff_player("", "70%", name="Marc Casadó")
    + ff_player("gerard-martin", "70%", "apercibido_box_min.png")
    + "</div>"
    '<div class="suplentes-container">'
    + ff_player("marc-bernal", "10%", "lesionado_box_min.png")
    + ff_player("ferran-torres", "5%", "duda_box_min.png", "sancionadoR_box_min.png")
    + ff_player("ansu-fati", "0%", unavailable="1")
    + ff_player("raphinha", "60%")
    + "</div>"
    '<section class="mod lesionados"><header>Estado físico de la plantilla</header>'
    + ff_absence(
        "frenkie-de-jong",
        "Frenkie de Jong",
        "lesionado_box_min.png",
        "Lesión de rodilla",
        "Desde 04/07 (73 días)",
        "Baja hasta principios de octubre",
    )
    + ff_absence(
        "pedri-gonzalez", "Pedri González", "lesionado_box_min.png", "Molestias en el pie"
    )
    + ff_absence(
        "gerard-martin",
        "Gerard Martín",
        "disponible_box_min.png",
        "Contusión en la nariz",
        "Disponible para la jornada 6",
    )
    + "</section>"
    '<section class="mod sancionados"></section>'
    '<section class="row mod team news">'
    '<div class="noticias bloque">'
    '<a href="https://www.futbolfantasy.com/laliga/noticias/151241-previa">'
    "15/09 03:32 Posibles alineaciones y previa fantasy del Barcelona - Racing</a>"
    '<a href="https://www.futbolfantasy.com/laliga/noticias/140000-invierno">'
    "20/12 10:00 Una noticia del invierno pasado</a>"
    '<a href="https://www.futbolfantasy.com/laliga/equipos/barcelona/noticias/1">Ver todas</a>'
    "</div></section>"
    "</body></html>"
)


def parsed() -> dict[str, object]:
    return {p.slug or p.name: p for p in parse_ff_team(FF_PAGE, NOW)[0]}


def test_futbolfantasy_reads_the_probable_eleven_then_the_rest_then_the_other_absentees() -> None:
    players, _ = parse_ff_team(FF_PAGE, NOW)
    assert [(p.slug, p.probability, p.starter) for p in players] == [
        ("raphinha", 60, True),
        ("pedri-gonzalez", 50, True),
        ("jules-kounde", 80, True),
        (None, 70, True),
        ("gerard-martin", 70, True),
        ("marc-bernal", 10, False),
        ("ferran-torres", 5, False),
        ("ansu-fati", 0, False),
        ("frenkie-de-jong", None, False),
    ]


def test_a_player_without_his_own_page_is_kept_by_his_printed_name() -> None:
    players, _ = parse_ff_team(FF_PAGE, NOW)
    # The label goes on with points, prices and minutes: the name ends at the first number.
    assert (players[3].slug, players[3].name) == (None, "Marc Casadó")
    assert players[0].name == "raphinha"


def test_futbolfantasy_takes_each_players_gravest_state() -> None:
    status = {key: p.status for key, p in parsed().items()}  # type: ignore[attr-defined]
    assert status == {
        "raphinha": "rotacion",
        # A doubt next to the shirt, an injury in the squad's physical state.
        "pedri-gonzalez": "lesionado",
        "jules-kounde": None,
        "Marc Casadó": None,
        # Back from injury: the report stays, the injury does not.
        "gerard-martin": "apercibido",
        "marc-bernal": "lesionado",
        "ferran-torres": "sancionado",
        "ansu-fati": "no_disponible",
        "frenkie-de-jong": "lesionado",
    }


def test_futbolfantasy_keeps_the_report_without_its_link_labels() -> None:
    notes = {key: p.note for key, p in parsed().items()}  # type: ignore[attr-defined]
    assert notes["frenkie-de-jong"] == (
        "Lesión de rodilla Desde 04/07 (73 días) Baja hasta principios de octubre"
    )
    assert notes["pedri-gonzalez"] == "Molestias en el pie"
    assert notes["gerard-martin"] == "Contusión en la nariz Disponible para la jornada 6"


def test_futbolfantasy_reads_the_team_news_with_their_date() -> None:
    _, news = parse_ff_team(FF_PAGE, NOW)
    assert [n.title for n in news] == [
        "Posibles alineaciones y previa fantasy del Barcelona - Racing",
        "Una noticia del invierno pasado",
    ]
    assert news[0].published_at == datetime(2026, 9, 15, 3, 32, tzinfo=MADRID)
    # No year on the page: a December headline read in September is last year's.
    assert news[1].published_at == datetime(2025, 12, 20, 10, 0, tzinfo=MADRID)


def test_a_changed_futbolfantasy_page_gives_nothing_rather_than_an_error() -> None:
    assert parse_ff_team("<html><body><p>Página nueva</p></body></html>", NOW) == ([], [])


LINEUP = {
    "home": {
        "teamId": 728,
        "formation": "alineacion_4-3-3",
        "players": [
            {
                "name": "Emil Audero",
                "slug": "e-audero-30441",
                "chance": 70,
                "esTitular": True,
                "positionId": 0,
                "playerExtras": None,
            },
            {
                "name": "Isi Palazón",
                "slug": "isi-palazon-131546",
                "chance": 0,
                "esTitular": False,
                "positionId": 3,
                "playerExtras": {
                    "status": "doubt",
                    "isSanctioned": False,
                    "statusInfo": "Molestias físicas",
                    "report": "Duda para la jornada 6",
                },
            },
        ],
    },
    "away": {
        "teamId": 540,
        "formation": "alineacion_4-4-2",
        "players": [
            {
                "name": "De Frutos",
                "slug": "jorge-de-frutos-128582",
                "chance": 0,
                "esTitular": False,
                "positionId": 3,
                "playerExtras": {
                    "status": None,
                    "isSanctioned": True,
                    "statusInfo": "Expulsado por roja directa",
                    "report": "Baja para las jornadas 5 y 6",
                },
            },
            {
                "name": "Batalla",
                "slug": "batalla-1",
                "chance": 0,
                "esTitular": False,
                "positionId": 3,
                "playerExtras": {
                    "status": "injured",
                    "isSanctioned": False,
                    "statusInfo": "Fractura",
                },
            },
        ],
    },
}
BLOB = (
    '1:["x"]\n72:["$","div",null,{"fixtureId":1,'
    '"homeTeam":{"id":728,"name":"Rayo Vallecano"},"awayTeam":{"id":540,"name":"Espanyol"}}]\n'
    '9:{"lineupBlock":' + json.dumps(LINEUP, ensure_ascii=False) + ',"after":{"x":"}"}}'
)


def af_page(blob: str) -> str:
    """The page as Next.js ships it: the payload split over pushed string chunks."""
    half = len(blob) // 2
    return "".join(
        f"<script>self.__next_f.push([1,{json.dumps(part)}])</script>"
        for part in (blob[:half], blob[half:])
    )


def test_analiticafantasy_reads_both_teams_from_the_embedded_data() -> None:
    result = parse_af_match(af_page(BLOB))
    assert result is not None
    home, away = result
    assert (home.name, home.formation, away.name, away.formation) == (
        "Rayo Vallecano",
        "4-3-3",
        "Espanyol",
        "4-4-2",
    )
    audero = home.players[0]
    assert (audero.name, audero.probability, audero.starter, audero.position) == (
        "Emil Audero",
        70,
        True,
        "POR",
    )


def test_analiticafantasy_reads_doubts_injuries_and_sanctions_with_their_reason() -> None:
    home, away = parse_af_match(af_page(BLOB)) or (None, None)
    assert home is not None and away is not None
    palazon = home.players[1]
    assert (palazon.status, palazon.note) == ("duda", "Molestias físicas · Duda para la jornada 6")
    assert [(p.name, p.status) for p in away.players] == [
        ("De Frutos", "sancionado"),
        ("Batalla", "lesionado"),
    ]


def test_an_unreadable_analiticafantasy_page_gives_nothing() -> None:
    assert parse_af_match("<html><body>sin datos</body></html>") is None
    assert parse_af_match(af_page('1:{"otra":"cosa"}')) is None


def test_analiticafantasy_lists_the_matchday_matches_once_each_in_order() -> None:
    html = (
        '<a href="/partido/100011991-atletico-madrid-real-madrid">Ver partido</a>'
        '<a href="/partido/100011992-athletic-club-alaves">Ver partido</a>'
        '<a href="/partido/100011991-atletico-madrid-real-madrid">otra vez</a>'
        '<a href="/equipo/barcelona-529">Barcelona</a>'
    )
    assert parse_af_matchday_links(html) == [
        "/partido/100011991-atletico-madrid-real-madrid",
        "/partido/100011992-athletic-club-alaves",
    ]


# --- predicted11 -------------------------------------------------------------------
# Hand-written to the structure seen on 15/09/2026: the ids in window.*, the
# tabs, and each team's «Ranking destacado» as li.p11-item rows. The key below
# is made up.

P11_KEY_JS = 'fetch(u,{auth:{id:"1234567890",apiToken:"0123456789abcdef0123456789abcdef"}})'


def p11_ranking(team: str, rows: list[tuple[str, int, str]]) -> str:
    items = "".join(
        f'<li class="p11-item"><span class="pos">{i}</span> <a href="#">{user}</a> '
        f"<span>{hits}</span> <span>{pct}%</span></li>"
        for i, (user, hits, pct) in enumerate(rows, start=1)
    )
    return f'<div class="card"><div class="card-header"><h5>Ranking destacado {team}</h5></div><ul>{items}</ul></div>'


def p11_page(
    home: tuple[str, int, list[tuple[str, int, str]]],
    away: tuple[str, int, list[tuple[str, int, str]]],
    matchday: int = 6,
) -> str:
    return (
        f"<script>window.currentTemporada = 143; window.jornada = {matchday};"
        f" window.equipoLocalId = {home[1]}; window.equipoVisitanteId = {away[1]};</script>"
        '<script src="/js/components/dynamic-auth.js?id=aa"></script>'
        '<script src="/js/partido-show.js?id=bb"></script>'
        '<ul class="nav nav-tabs">'
        f'<li><button data-bs-target="#equipo-local">{home[0]}</button></li>'
        f'<li><button data-bs-target="#equipo-visitante">{away[0]}</button></li></ul>'
        + p11_ranking(home[0], home[2])
        + p11_ranking(away[0], away[2])
    )


def p11_lineup(user: str, *players: tuple[str, str]) -> str:
    return json.dumps(
        {
            "username": user,
            "porcentaje": "83.64",
            "fecha_actualizacion": "2026-09-13 12:57:00",
            "participacion": [
                {"id": i, "nombre": name, "nombreCorto": name.split()[-1], "posicion": pos}
                for i, (name, pos) in enumerate(players, start=1)
            ],
        }
    )


RAYO_TOP = [("watusi74", 46, "83.64"), ("PilaAlcalinaAAA", 45, "81.82"), ("Aroodii", 44, "80")]
ESPANYOL_TOP = [("huugo_21", 55, "83.33")]


def test_predicted11_reads_both_teams_ranking_with_their_ids() -> None:
    match = parse_p11_match(
        p11_page(
            ("Rayo Vallecano", 14, [*RAYO_TOP, ("cuarto", 40, "70")]),
            ("Espanyol", 5, ESPANYOL_TOP),
        )
    )
    assert match is not None
    assert (match.season, match.matchday) == (143, 6)
    rayo, espanyol = match.sides
    assert (rayo.name, rayo.team_id, espanyol.name, espanyol.team_id) == (
        "Rayo Vallecano",
        14,
        "Espanyol",
        5,
    )
    assert [p.username for p in rayo.featured][:3] == ["watusi74", "PilaAlcalinaAAA", "Aroodii"]
    assert (rayo.featured[0].rank, rayo.featured[0].hits, rayo.featured[0].pct) == (1, 46, 83.64)
    assert espanyol.featured[0].pct == 83.33


def test_predicted11_finds_the_script_with_the_visitor_key() -> None:
    page = p11_page(("Rayo Vallecano", 14, RAYO_TOP), ("Espanyol", 5, ESPANYOL_TOP))
    assert parse_p11_script_path(page) == "/js/partido-show.js?id=bb"
    assert parse_p11_guest_key(P11_KEY_JS) == "1234567890-0123456789abcdef0123456789abcdef"
    assert parse_p11_guest_key("var nothing = 1;") is None


def test_predicted11_reads_a_predictors_eleven() -> None:
    lineup = parse_p11_lineup(
        p11_lineup("watusi74", ("Augusto Batalla", "Portero"), ("Andrei Ratiu", "Defensa"))
    )
    assert lineup is not None
    assert lineup.username == "watusi74"
    assert [(p.name, p.position, p.probability, p.starter) for p in lineup.players] == [
        ("Augusto Batalla", "POR", 100, True),
        ("Andrei Ratiu", "DEF", 100, True),
    ]


def test_a_changed_predicted11_page_or_answer_gives_nothing() -> None:
    assert parse_p11_match("<html><body>Mantenimiento</body></html>") is None
    # Ids but no teams.
    assert (
        parse_p11_match(
            "<script>window.currentTemporada = 143; window.jornada = 6;"
            " window.equipoLocalId = 1; window.equipoVisitanteId = 2;</script>"
        )
        is None
    )
    assert parse_p11_lineup("<html>error</html>") is None
    assert parse_p11_lineup("[]") is None
    empty = parse_p11_lineup('{"username": "x", "participacion": []}')
    assert empty is not None and empty.players == []
