"""The lineup chat's tools read the asker's own squad, whatever the model sends."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineup_assistant.context import LineupContext
from src.features.lineup_assistant.tools import NOT_A_PARTICIPANT, build_tools
from src.shared.assistant.tools import run_tool
from src.shared.models.player import Player
from src.shared.models.player_availability import PlayerAvailability
from src.shared.models.team import Team

SCOPE_WORDS = {
    "season_id",
    "temporada",
    "matchday",
    "jornada",
    "participant_id",
    "participante",
    "user_id",
    "usuario",
}


def context(db: AsyncSession, league: SimpleNamespace, **kw: object) -> LineupContext:
    ctx = LineupContext(
        session=db,
        season_id=league.season.id,
        matchday=6,
        user_id=kw.pop("user_id", league.me.id),  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )
    ctx._predictions = league.predictions
    return ctx


async def call(ctx: LineupContext, name: str, **arguments: object) -> str:
    return await run_tool(build_tools(ctx), name, arguments)


async def test_no_tool_lets_the_model_choose_season_matchday_or_participant(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    for spec in build_tools(context(db_session, league)):
        assert not set(spec.parameters["properties"]) & SCOPE_WORDS, spec.name


async def test_a_scope_sent_by_the_model_is_ignored(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    out = await call(
        context(db_session, league),
        "mi_plantilla",
        season_id=999,
        user_id=league.rival.id,
        participante="Lucia",
    )
    assert "Pedri" in out
    assert "Dani Cardenas" not in out


async def test_my_squad_carries_forecast_sources_and_fixture(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    out = await call(context(db_session, league), "mi_plantilla")
    lines = {line.split(" | ")[0]: line for line in out.splitlines()}
    assert "15 jugadores" in out and "Todavia no hay once guardado" in out
    assert "vs Racing (casa)" in lines["Pedri"]
    assert "FF 50 % titular, duda" in lines["Pedri"]
    assert "parte: Molestias en el pie" in lines["Pedri"]
    assert "FF 80 % (antes 60 %)" in lines["Raphinha"] and "AF 70 %" in lines["Raphinha"]
    assert "[penaltis]" in lines["Raphinha"]
    assert "lesionado" in lines["Frenkie de Jong"]
    assert "7.0 (7.0)" in lines["Raphinha"] and "2.4 (4.0)" in lines["Javi Puado"]
    assert "sin datos de las webs" in lines["Jules Kounde"]


async def test_the_proposed_eleven_leaves_the_injured_out_and_explains_itself(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    out = await call(context(db_session, league), "proponer_once")
    head, *rows = out.splitlines()
    eleven = rows[: rows.index("Fuera del once, los de mas valor:")]
    names = {row.split(" | ")[1] for row in eleven}
    assert len(eleven) == 11 and head.startswith("Once propuesto: 1-")
    assert "Frenkie de Jong" not in names
    assert {"Raphinha", "Joan Garcia"} <= names
    raphinha = next(r for r in eleven if "Raphinha" in r)
    assert "5.2 = 7.0 si juega x 75%" in raphinha and "AF 70 % · FF 80 %" in raphinha
    # Worth 6.0 if he plays, but futbolfantasy gives him 50 %: sure starters win.
    assert "Pedri" not in names
    assert "MED | Pedri | Barcelona | 3.0 = 6.0 si juega x 50%" in out
    # Without a source, recent history decides; and it is not discounted twice.
    assert "Javi Puado | Espanyol | 2.4 = 4.0 si juega x 60%" in out


async def test_a_formation_can_be_asked_for_and_a_wrong_one_is_named(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    ctx = context(db_session, league)
    assert (await call(ctx, "proponer_once", formacion="1-5-3-2")).startswith(
        "Once propuesto: 1-5-3-2"
    )
    wrong = await call(ctx, "proponer_once", formacion="1-2-2-6")
    assert wrong.startswith("Formacion no valida") and "1-4-4-2" in wrong


async def test_availability_by_player_and_by_team_including_the_unmatched(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    ctx = context(db_session, league)
    assert "Indica" in await call(ctx, "disponibilidad")
    pedri = await call(ctx, "disponibilidad", jugador="pedri")
    assert "FF 50 %" in pedri and "Molestias en el pie" in pedri
    rayo = await call(ctx, "disponibilidad", equipo="rayo")
    assert "Batalla (no emparejado con nuestra base)" in rayo and "Fractura" in rayo


async def test_rival_lineups_show_the_playoff_rival_and_hide_names_by_default(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    out = await call(context(db_session, league), "alineaciones_rivales")
    rival = f"Participante {league.parts['rival'].id} (TU RIVAL DE PLAYOFF esta jornada): 1-4-4-2"
    assert rival in out
    assert "POR Dani Cardenas; DEL Jorge de Frutos" in out
    assert f"Participante {league.parts['other'].id}: sin alineacion guardada" in out
    assert f"Participante {league.parts['me'].id}" not in out
    assert "Lucia" not in out
    named = await call(
        context(db_session, league, anonymize_participants=False), "alineaciones_rivales"
    )
    assert "Lucia (TU RIVAL DE PLAYOFF" in named


async def test_calendar_rules_news_and_history(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    ctx = context(db_session, league)
    calendar = await call(ctx, "calendario_jornada")
    assert "Cierre de alineaciones: dom 20/09 15:45" in calendar
    assert "dom 20/09 16:15 | Barcelona - Racing" in calendar
    assert "Rayo Vallecano - Espanyol (no puntua)" in calendar
    rules = await call(ctx, "reglas")
    assert (
        "1-3-4-3, 1-4-3-3, 1-4-4-2, 1-5-3-2" in rules
        and "gol [DEL]: 5 (Gol de delantero)" in rules
    )
    news = await call(ctx, "noticias_equipo", equipo="Barcelona")
    assert "Posibles alineaciones del Barcelona - Racing" in news and "151241-previa" in news
    history = await call(ctx, "historial_jugador", jugador="raphinha")
    assert "J5: 90' | 12 pts | Marca 2 | AS 3 | goles 1" in history
    assert "sin partidos registrados" in await call(ctx, "historial_jugador", jugador="kounde")


async def test_news_from_elsewhere_is_refused_by_the_tool(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    out = await call(context(db_session, league), "leer_noticia", url="https://example.com/x")
    assert out.startswith("No se puede leer ese enlace")


async def test_someone_outside_the_season_has_no_squad(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    ctx = context(db_session, league, user_id=league.stranger.id)
    assert await call(ctx, "mi_plantilla") == NOT_A_PARTICIPANT
    assert await call(ctx, "proponer_once") == NOT_A_PARTICIPANT


async def test_a_predicted11_eleven_counts_for_who_is_in_it_and_against_who_is_not(
    db_session: AsyncSession, league: SimpleNamespace
) -> None:
    barcelona = (
        await db_session.execute(
            select(Team).where(Team.season_id == league.season.id, Team.name == "Barcelona")
        )
    ).scalar_one()
    raphinha = (
        await db_session.execute(
            select(Player).where(
                Player.season_id == league.season.id, Player.display_name == "Raphinha"
            )
        )
    ).scalar_one()
    who = "watusi74, 1.º del destacado del Barcelona (80,0 % de acierto)"
    db_session.add(
        PlayerAvailability(
            season_id=league.season.id,
            matchday_number=6,
            source="predicted11_1",
            team_id=barcelona.id,
            player_id=raphinha.id,
            raw_name="Raphinha",
            probability=100,
            starter=True,
            note=who,
        )
    )
    await db_session.flush()
    ctx = context(db_session, league)

    squad = await call(ctx, "mi_plantilla")
    lines = {line.split(" | ")[0]: line for line in squad.splitlines()}
    assert f"P11 1/1 (le ponen: {who})" in lines["Raphinha"]
    assert "P11 0/1" in lines["Pedri"]
    # The predictor's note is not a report on the player.
    assert "parte:" not in lines["Raphinha"]
    assert "parte: Molestias en el pie" in lines["Pedri"]

    proposal = await call(context(db_session, league), "proponer_once")
    assert "AF 70 % · FF 80 % · P11 1/1" in proposal
    # Left out of that eleven: FF 50 % and P11 0 make 25 %.
    assert "MED | Pedri | Barcelona | 1.5 = 6.0 si juega x 25%" in proposal

    team = await call(context(db_session, league), "disponibilidad", equipo="barcelona")
    assert "P11 le pone en su once" in team
    assert f"Once de predicted11 para Barcelona: {who}" in team
