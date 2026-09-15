"""The tools the lineup chat can call.

All of them read; none writes, and none takes a season, matchday or participant
from the model — those come from the request context. Handlers return compact
plain text: about half the tokens of JSON, and the model reads it as well.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

import httpx

from src.core.exceptions import NotFoundError
from src.features.lineup_assistant.context import LineupContext
from src.features.lineup_assistant.news_reader import NewsUrlError, read_article
from src.features.lineup_assistant.optimizer import (
    P11_PREFIX,
    POSITIONS,
    SOURCE_LABELS,
    Suggestion,
    Valued,
)
from src.features.lineup_assistant.repository import LineupAssistantRepository
from src.features.lineup_intel.matching import normalize
from src.features.lineup_intel.parsers import MADRID
from src.features.lineup_intel.schemas import SourceReading
from src.features.lineups.service import LineupService
from src.features.stats.fixtures import difficulty
from src.shared.assistant.tools import ToolSpec, guarded
from src.shared.lineup_deadline import effective_deadline

_DAYS = ("lun", "mar", "mie", "jue", "vie", "sab", "dom")
_ORDER = {p: i for i, p in enumerate(POSITIONS)}
NOT_A_PARTICIPANT = (
    "Quien pregunta no participa en esta temporada: no tiene plantilla que alinear."
)


def when(moment: datetime | None) -> str:
    if moment is None:
        return "sin hora"
    local = moment.astimezone(MADRID)
    return f"{_DAYS[local.weekday()]} {local:%d/%m %H:%M}"


def _num(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def source_bit(
    source: str,
    probability: int | None,
    previous: int | None,
    starter: bool,
    status: str | None,
    fetched_at: datetime | None,
) -> str:
    """ "FF 70 % (antes 50 %) titular, duda [lun 15/09 18:00]"."""
    if source.startswith(P11_PREFIX):
        return f"P11 le pone en su once [{when(fetched_at)}]"
    pct = f"{probability} %" if probability is not None else "sin %"
    if previous is not None and previous != probability:
        pct += f" (antes {previous} %)"
    state = f", {status.replace('_', ' ')}" if status else ""
    role = "titular" if starter else "suplente"
    return f"{SOURCE_LABELS.get(source, source)} {pct} {role}{state} [{when(fetched_at)}]"


def readings_text(readings: list[SourceReading], p11_covered: Collection[str] = ()) -> str:
    """The sources in a line. predicted11's elevens go together: "P11 2/3 (le
    ponen: watusi74, 1.º del destacado…)". ``p11_covered`` are the predictors
    with an eleven for his team, so the count includes those who leave him out."""
    plain = [r for r in readings if not r.source.startswith(P11_PREFIX)]
    picks = sorted(
        (r for r in readings if r.source.startswith(P11_PREFIX)), key=lambda r: r.source
    )
    bits = [
        source_bit(
            r.source, r.probability, r.previous_probability, r.starter, r.status, r.fetched_at
        )
        for r in plain
    ]
    covered = set(p11_covered) | {r.source for r in picks}
    if covered:
        who = "; ".join(r.note or r.source for r in picks)
        bits.append(f"P11 {len(picks)}/{len(covered)}" + (f" (le ponen: {who})" if picks else ""))
    return " · ".join(bits) if bits else "sin datos de las webs"


def valued_line(v: Valued) -> str:
    c = v.candidate
    if c.xpts_if_plays is None:
        calc = "0"
    else:
        calc = f"{v.value:.1f} = {c.xpts_if_plays:.1f} si juega x {v.play_prob:.0%}"
    return f"{c.position} | {c.name} | {c.team_name} | {calc} | {v.basis}"


def suggestion_text(s: Suggestion) -> str:
    lines = [
        f"Once propuesto: {s.formation}, valor esperado {s.total:.1f} puntos "
        "(puntos si juega x probabilidad de jugar):"
    ]
    lines += [valued_line(v) for v in s.eleven]
    if s.bench:
        lines.append("Fuera del once, los de mas valor:")
        lines += [valued_line(v) for v in s.bench[:5]]
    return "\n".join(lines)


def _pick(needle: str, names: list[str]) -> list[int]:
    want = normalize(needle)
    return [i for i, name in enumerate(names) if want and want in normalize(name)]


def build_tools(ctx: LineupContext) -> list[ToolSpec]:
    repo = LineupAssistantRepository(ctx.session)

    async def mi_plantilla() -> str:
        try:
            squad = await ctx.squad()
        except NotFoundError:
            return NOT_A_PARTICIPANT
        predictions = await ctx.predictions()
        readings = await ctx.readings()
        fixtures = await ctx.fixtures()
        covered = await ctx.p11_coverage()
        current = squad.current_lineup
        in_eleven = {p.player_id for p in current.players} if current else set()
        saved = (
            f"Once guardado: {current.formation}." if current else "Todavia no hay once guardado."
        )
        lines = [
            f"Tu plantilla para la jornada {ctx.matchday} ({len(squad.squad)} jugadores). {saved}",
            "Nombre | Pos | Equipo | Partido | Pts temporada | Ultimas 5 (- no jugo) | "
            "xPts (si juega) | Titular historico | Alineaciones probables",
        ]
        for p in sorted(squad.squad, key=lambda s: (_ORDER.get(s.position, 9), s.display_name)):
            forecast = predictions.get(p.player_id)
            if p.opponent_team_name:
                match = f"vs {p.opponent_team_name} ({'casa' if p.is_home else 'fuera'})"
                fixture = fixtures.get(p.team_name)
                if fixture is not None:
                    match += f", {difficulty(p.position, fixture)}"
            else:
                match = "sin partido esta jornada"
            form = "-"
            if p.recent_form:
                form = ",".join(str(m.points) if m.played else "-" for m in p.recent_form.matches)
            xpts = (
                f"{_num(forecast.xpts)} ({_num(forecast.xpts_if_plays)})"
                if forecast
                else "sin prevision"
            )
            starter = f"{forecast.starter_pct:.0f} %" if forecast else "-"
            said = readings.get(p.player_id, [])
            # predicted11's note says who the predictor is, not how the player is.
            note = next(
                (r.note for r in said if r.note and not r.source.startswith(P11_PREFIX)), None
            )
            flags = []
            if forecast and forecast.is_penalty_taker:
                flags.append("penaltis")
            if p.player_id in in_eleven:
                flags.append("EN TU ONCE")
            lines.append(
                f"{p.display_name} | {p.position} | {p.team_name} | {match} | {p.season_points} | "
                f"{form} | {xpts} | {starter} | "
                f"{readings_text(said, covered.get(p.team_name, ()))}"
                + (f" · parte: {note[:120]}" if note else "")
                + (f" [{', '.join(flags)}]" if flags else "")
            )
        return "\n".join(lines)

    async def disponibilidad(jugador: str | None = None, equipo: str | None = None) -> str:
        if not jugador and not equipo:
            return "Indica un jugador o un equipo."
        rows = await repo.availability(ctx.season_id, ctx.matchday)
        if not rows:
            return (
                f"Todavia no hay lecturas de las webs para la jornada {ctx.matchday}. Se leen "
                "solas en las 48 h previas al cierre, o con el boton Actualizar."
            )
        want_player = normalize(jugador or "")
        want_team = normalize(equipo or "")
        hits = [
            r
            for r in rows
            if (
                not want_player
                or want_player in normalize(r.player_name or "")
                or want_player in normalize(r.reading.raw_name)
            )
            and (not want_team or want_team in normalize(r.team_name))
        ]
        if not hits:
            return "Ninguna lectura coincide con eso."
        lines = []
        for r in hits[:40]:
            a = r.reading
            name = r.player_name or f"{a.raw_name} (no emparejado con nuestra base)"
            bit = source_bit(
                a.source, a.probability, a.previous_probability, a.starter, a.status, a.fetched_at
            )
            lines.append(f"{name} | {r.team_name} | {bit}" + (f" | {a.note}" if a.note else ""))
        if len(hits) > 40:
            lines.append(f"(y {len(hits) - 40} lecturas mas: concreta)")
        # Who has an eleven for those teams: whoever of them does not list a
        # player leaves him out.
        teams = {r.team_name for r in hits}
        for item in (await ctx.intel()).coverage:
            if item.team_name in teams:
                lines.append(
                    f"Once de predicted11 para {item.team_name}: {item.note or item.source}"
                )
        return "\n".join(lines)

    async def noticias_equipo(equipo: str) -> str:
        rows = await repo.news(ctx.season_id)
        hits = [rows[i] for i in _pick(equipo, [r.team_name for r in rows])][:8]
        if not hits:
            return f"No hay titulares guardados de '{equipo}'."
        return "\n".join(
            f"{when(r.item.published_at)} | {r.team_name} | "
            f"{SOURCE_LABELS.get(r.item.source, r.item.source)} | {r.item.title} | {r.item.url}"
            for r in hits
        )

    async def leer_noticia(url: str) -> str:
        try:
            return await read_article(url)
        except NewsUrlError as exc:
            return f"No se puede leer ese enlace: {exc}"
        except httpx.HTTPError:
            return "No se ha podido descargar la noticia: la web no responde o da error."

    async def prediccion(jugador: str) -> str:
        forecasts = list((await ctx.predictions()).values())
        hits = [forecasts[i] for i in _pick(jugador, [p.player_name for p in forecasts])]
        if not hits:
            return f"Sin prevision para '{jugador}' esta jornada: no lo encuentro o su equipo no juega."
        if len(hits) > 5:
            names = ", ".join(p.player_name for p in hits[:10])
            return f"'{jugador}' es ambiguo ({len(hits)} coincidencias): {names}. Concreta mas."
        return "\n".join(
            f"{p.player_name} | {p.position} | {p.team_name} vs {p.opponent_name} "
            f"({'casa' if p.is_home else 'fuera'}) | xPts {p.xpts} (si juega {p.xpts_if_plays}; "
            f"suelo {p.xpts_floor}, techo {p.xpts_ceiling}) | media temporada {p.season_avg} | "
            f"forma {_num(p.form_5)} | media {'en casa' if p.is_home else 'fuera'} "
            f"{_num(p.location_avg)} | factor rival {p.rival_factor} | tendencia {p.trend} | "
            f"confianza {p.confidence} | titular {p.starter_pct:.0f} % de sus ultimos partidos | "
            f"{p.matchdays_played} jornadas jugadas"
            + (" | lanza penaltis" if p.is_penalty_taker else "")
            for p in hits
        )

    async def historial_jugador(jugador: str, jornadas: int = 5) -> str:
        players = await repo.players(ctx.season_id)
        hits = [players[i] for i in _pick(jugador, [p.name for p in players])]
        if not hits:
            return f"No encuentro a '{jugador}' en esta temporada."
        if len(hits) > 3:
            names = ", ".join(f"{p.name} ({p.team_name})" for p in hits[:10])
            return f"'{jugador}' es ambiguo ({len(hits)} coincidencias): {names}. Concreta mas."
        out = []
        for p in hits:
            rows = await repo.history(p.id, jornadas)
            head = f"{p.name} ({p.position}, {p.team_name}):"
            if not rows:
                out.append(f"{head} sin partidos registrados esta temporada.")
                continue
            body = []
            for h in rows:
                if not h.played:
                    body.append(f"J{h.matchday}: no jugo")
                    continue
                cards = " | roja" if h.red else (" | amarilla" if h.yellow else "")
                body.append(
                    f"J{h.matchday}: {h.minutes or 0}' | {h.points} pts | Marca {h.marca or '-'} | "
                    f"AS {h.as_picas or '-'} | goles {h.goals} | asist {h.assists}{cards}"
                )
            out.append(head + "\n" + "\n".join(body))
        return "\n\n".join(out)

    async def calendario_jornada() -> str:
        matchday = await repo.matchday(ctx.season_id, ctx.matchday)
        season = await repo.season(ctx.season_id)
        if matchday is None or season is None:
            return f"No existe la jornada {ctx.matchday} en esta temporada."
        deadline = effective_deadline(matchday, season.lineup_deadline_min)
        head = f"Jornada {ctx.matchday}. Cierre de alineaciones: {when(deadline)}."
        if not matchday.counts:
            head += " ESTA JORNADA NO PUNTUA."
        rows = await repo.calendar(ctx.season_id, ctx.matchday)
        lines = [head] + [
            f"{when(r.played_at)} | {r.home} - {r.away}" + ("" if r.counts else " (no puntua)")
            for r in rows
        ]
        return "\n".join(lines)

    async def alineaciones_rivales() -> str:
        try:
            me: int | None = (await ctx.squad()).participant_id
        except NotFoundError:
            me = None
        lineups = await LineupService(ctx.session).get_admin_matchday_lineups(
            ctx.season_id, ctx.matchday
        )
        matchday = await repo.matchday(ctx.season_id, ctx.matchday)
        rival = (
            await repo.playoff_rival(matchday.id, me)
            if matchday is not None and me is not None
            else None
        )
        lines = []
        for p in lineups.participants:
            if p.participant_id == me:
                continue
            label = ctx.participant_label(p.participant_id, p.display_name)
            if p.participant_id == rival:
                label += " (TU RIVAL DE PLAYOFF esta jornada)"
            if not p.has_lineup or not p.players:
                lines.append(f"{label}: sin alineacion guardada todavia.")
                continue
            by_position: dict[str, list[str]] = {}
            for player in sorted(p.players, key=lambda x: x.display_order):
                by_position.setdefault(player.position_slot, []).append(player.display_name)
            squad = "; ".join(
                f"{pos} {', '.join(by_position[pos])}" for pos in POSITIONS if pos in by_position
            )
            lines.append(f"{label}: {p.formation} | {squad} | guardada {when(p.confirmed_at)}")
        return "\n".join(lines) or "Nadie mas ha guardado alineacion esta jornada."

    async def proponer_once(formacion: str | None = None) -> str:
        names = [f.name for f in await ctx.formations()]
        if formacion and formacion not in names:
            return f"Formacion no valida: {formacion}. Validas: {', '.join(names)}."
        try:
            suggestion = await ctx.suggestion(formacion)
        except NotFoundError:
            return NOT_A_PARTICIPANT
        if suggestion is None:
            return (
                f"Con esta plantilla no se puede formar {formacion or 'ninguna formacion valida'}."
            )
        return suggestion_text(suggestion)

    async def reglas() -> str:
        formations = await ctx.formations()
        season = await repo.season(ctx.season_id)
        rules = await repo.scoring_rules(ctx.season_id)
        lines = [
            "Alineacion: 1 portero + 10 de campo, en una de estas formaciones: "
            + ", ".join(f.name for f in formations)
            + ".",
        ]
        if season is not None:
            lines.append(
                f"Cierre: {season.lineup_deadline_min} minutos antes del primer partido que puntua."
            )
        if rules:
            lines.append("Puntuacion de esta temporada:")
            lines += [
                f"{r.rule_key}{f' [{r.position}]' if r.position else ''}: {float(r.value):g}"
                + (f" ({r.description})" if r.description else "")
                for r in rules
            ]
        return "\n".join(lines)

    def spec(name: str, description: str, properties: dict, required: list[str], fn) -> ToolSpec:  # type: ignore[no-untyped-def]
        return ToolSpec(
            name=name,
            description=description,
            parameters={"type": "object", "properties": properties, "required": required},
            handler=guarded(ctx.session, fn),
        )

    nombre = {"type": "string", "description": "Nombre o parte del nombre."}
    return [
        spec(
            "mi_plantilla",
            "Tu plantilla para esta jornada: por jugador, posicion, equipo, rival (casa/fuera "
            "y dificultad), puntos, ultimas 5 jornadas, xPts, titularidad historica, "
            "penaltis y lo que dicen las alineaciones probables (FF/AF: %, estado, parte). "
            "Llamala primero para casi cualquier pregunta sobre tu once.",
            {},
            [],
            mi_plantilla,
        ),
        spec(
            "disponibilidad",
            "Detalle de las alineaciones probables de futbolfantasy (FF) y analiticafantasy "
            "(AF) de esta jornada: % de titular, cambio desde la lectura anterior, estado, "
            "parte medico y hora de lectura. Por jugador o por equipo (incluye los que no "
            "estan en tu plantilla).",
            {
                "jugador": nombre,
                "equipo": {"type": "string", "description": "Equipo de La Liga (parcial)."},
            },
            [],
            disponibilidad,
        ),
        spec(
            "noticias_equipo",
            "Titulares recientes de un equipo guardados de futbolfantasy, con fecha y enlace.",
            {"equipo": {"type": "string", "description": "Equipo de La Liga (parcial)."}},
            ["equipo"],
            noticias_equipo,
        ),
        spec(
            "leer_noticia",
            "Texto de una noticia concreta. Solo enlaces https de futbolfantasy.com o "
            "analiticafantasy.com (por ejemplo, los de noticias_equipo).",
            {"url": {"type": "string", "description": "Enlace completo https."}},
            ["url"],
            leer_noticia,
        ),
        spec(
            "prediccion",
            "Prevision del modelo interno para un jugador en esta jornada: xPts, si juega, "
            "suelo y techo, media, forma, media en casa/fuera, factor rival, tendencia, "
            "confianza, titularidad historica y penaltis.",
            {"jugador": nombre},
            ["jugador"],
            prediccion,
        ),
        spec(
            "historial_jugador",
            "Ultimas jornadas reales de un jugador: minutos, puntos, nota Marca y AS, goles, "
            "asistencias y tarjetas.",
            {
                "jugador": nombre,
                "jornadas": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Cuantas jornadas (1-10, por defecto 5).",
                },
            },
            ["jugador"],
            historial_jugador,
        ),
        spec(
            "calendario_jornada",
            "Partidos de esta jornada con dia y hora, cuales no puntuan, y la hora de cierre "
            "de alineaciones.",
            {},
            [],
            calendario_jornada,
        ),
        spec(
            "alineaciones_rivales",
            "Alineaciones que los demas participantes ya han guardado esta jornada, y quien es "
            "tu rival de playoff si lo hay.",
            {},
            [],
            alineaciones_rivales,
        ),
        spec(
            "proponer_once",
            "El once de mas valor esperado de tu plantilla: puntos si juega x probabilidad de "
            "jugar (alineaciones probables o, si no hay, titularidad historica; lesionados y "
            "sancionados fuera), en la mejor formacion valida o en la que indiques. Explica "
            "cada eleccion.",
            {
                "formacion": {
                    "type": "string",
                    "pattern": "^1-[0-9]-[0-9]-[0-9]$",
                    "description": "Formacion a imponer, p. ej. 1-4-4-2. Omitir para la mejor.",
                }
            },
            [],
            proponer_once,
        ),
        spec(
            "reglas",
            "Reglas de la alineacion: formaciones validas, cierre y puntuacion de la temporada.",
            {},
            [],
            reglas,
        ),
    ]
