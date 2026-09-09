"""The six tools the draft assistant can call.

Every one of them reads through the services the UI already uses
(``DraftValueService``, ``DraftService``), so the chat and the board can never
disagree. None of them writes. None of them takes a season, draft or
participant id from the model — those come from the request context below.

Handlers return compact plain text rather than JSON: it costs roughly half the
tokens for the same information and the model reads it just as well.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.draft_assistant.tools import ToolSpec
from src.features.drafts.schemas import DraftDetailResponse
from src.features.drafts.service import DraftService
from src.features.stats.schemas_draft import DraftValuePlayer, DraftValueResponse
from src.features.stats.scorecard import STARTER_SLOTS
from src.features.stats.service_draft import DraftValueService

POSITIONS = ("POR", "DEF", "MED", "DEL")

# Measured over the 8 real seasons in the migrated history (final points,
# matchdays.counts AND matches.counts respected). Replacement = participants x
# starter slots. See docs/DRAFT_ASSISTANT.md section 7 for the full method.
HISTORICAL_SCARCITY = """\
Escasez posicional medida sobre 8 temporadas reales de esta liga
(puntos finales; reemplazo = participantes x plazas de titular POR1/DEF4/MED3/DEL3):

Pos | Excedente del 1o sobre el reemplazo | Coste de esperar al 3o | al 6o
DEL | 193 | 70 | 105
DEF | 118 | 28 |  49
POR | 116 | 47 |  76
MED |  97 | 25 |  44

Lecturas:
1. El mejor DEL vale ~77 puntos mas de excedente que el mejor POR, y gana en las
   8 temporadas sin excepcion. Con pick temprano, si queda un DEL top, es el.
2. POR es la SEGUNDA posicion mas escasa, no la ultima: esperar del 1o al 3o
   cuesta 47 puntos, frente a 28 en DEF y 25 en MED. "La porteria puede esperar"
   es FALSO.
3. Orden real de urgencia: DEL >> POR > DEF ~ MED.
4. En 6 de 8 temporadas el portero mas puntuado fue del Madrid, Barca o Atletico
   (Oblak x3, Courtois x2, ter Stegen x1). Pero solo la mitad de los top-3: David
   Soria (Getafe) sale 2 veces, y tambien Unai Simon, Remiro, Bono y Radu.

Caveats: son puntos reales (retrospectiva), asi que mide la FORMA de la curva, no
el acierto al elegir. Los porteros son mas predecibles (juegan todo, siguen a la
defensa del equipo), lo que juega ligeramente a su favor frente a la tabla."""


@dataclass
class AssistantContext:
    """Everything the tools are allowed to touch, fixed by the caller.

    The model can influence the arguments of a tool, never these. Memoised
    because the board is a heavy computation and one question can trigger
    several tool calls.
    """

    session: AsyncSession
    season_id: int
    phase: str
    anonymize_participants: bool = True
    _board: DraftValueResponse | None = field(default=None, init=False, repr=False)
    _draft: DraftDetailResponse | None = field(default=None, init=False, repr=False)

    async def board(self) -> DraftValueResponse:
        if self._board is None:
            self._board = await DraftValueService(self.session).get_draft_values(self.season_id)
        return self._board

    async def draft(self) -> DraftDetailResponse:
        if self._draft is None:
            self._draft = await DraftService(self.session).get_draft_detail(
                self.season_id, self.phase
            )
        return self._draft

    def participant_label(self, participant_id: int, display_name: str) -> str:
        """Names of other people are not needed for the reasoning, so by default
        they do not leave the server. Set ASSISTANT_ANONYMIZE_PARTICIPANTS=false
        to send real names instead."""
        if not self.anonymize_participants:
            return display_name
        return f"Participante {participant_id}"


def _fmt(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _player_row(p: DraftValuePlayer) -> str:
    flags = []
    if p.is_drafted:
        flags.append("FICHADO")
    if p.is_bench_risk:
        flags.append("banquillo")
    if p.is_peak_year:
        flags.append("pico")
    if p.is_new:
        flags.append("nuevo")
    extra = f" [{', '.join(flags)}]" if flags else ""
    tags = f" tags={','.join(p.tags)}" if p.tags else ""
    return (
        f"{p.display_name} | {p.position} | {p.team_name} | "
        f"Prio {_fmt(p.priority)} | Base {_fmt(p.priority_base)} | "
        f"VORP {_fmt(p.vorp, 2)} | Salto {_fmt(p.next_gap)} | "
        f"Tier {p.position_tier or '-'} | Disp {_fmt(p.participation, 2)}"
        f"{tags}{extra}"
    )


def build_tools(ctx: AssistantContext) -> list[ToolSpec]:
    async def buscar_jugadores(
        posicion: str | None = None,
        equipo: str | None = None,
        solo_disponibles: bool = True,
        orden: str = "prioridad",
        limite: int = 20,
    ) -> str:
        board = await ctx.board()
        rows = list(board.players)
        if posicion:
            rows = [p for p in rows if p.position == posicion.upper()]
        if equipo:
            needle = equipo.lower()
            rows = [p for p in rows if needle in p.team_name.lower()]
        if solo_disponibles:
            rows = [p for p in rows if not p.is_drafted]

        key = (lambda p: p.vorp or -1e9) if orden == "vorp" else (lambda p: p.priority or -1e9)
        rows.sort(key=key, reverse=True)
        rows = rows[:limite]

        if not rows:
            return "Sin resultados con esos filtros."
        header = f"{len(rows)} jugadores (orden: {orden}):"
        return header + "\n" + "\n".join(_player_row(p) for p in rows)

    async def detalle_jugador(nombre: str) -> str:
        board = await ctx.board()
        needle = nombre.lower().strip()
        matches = [p for p in board.players if needle in p.display_name.lower()]
        if not matches:
            return f"No encuentro ningun jugador que contenga '{nombre}'."
        if len(matches) > 5:
            names = ", ".join(p.display_name for p in matches[:10])
            return f"'{nombre}' es ambiguo ({len(matches)} coincidencias): {names}. Concreta mas."
        out = []
        for p in matches:
            out.append(
                f"{p.display_name} ({p.position}, {p.team_name})\n"
                f"  Prioridad {_fmt(p.priority)} (base sin tags {_fmt(p.priority_base)}), "
                f"puesto global {p.overall_rank or '-'}\n"
                f"  VORP {_fmt(p.vorp, 2)} | Salto {_fmt(p.next_gap)} | "
                f"rank en su posicion {p.position_rank or '-'} | Tier {p.position_tier or '-'}\n"
                f"  Participacion {_fmt(p.participation, 2)} | "
                f"partidos restantes esperados {_fmt(p.exp_games_remaining)} | "
                f"puntos proyectados resto {_fmt(p.proj_rest_points)}\n"
                f"  Fiabilidad (event_share) {_fmt(p.event_share, 2)} | "
                f"goles encajados/partido del equipo {_fmt(p.team_goals_conceded, 2)}\n"
                f"  Historico: {p.games_played} partidos en {p.seasons_played} temporadas, "
                f"media {_fmt(p.avg_points)}, {p.goals} goles, {p.assists} asistencias\n"
                f"  Marca {_fmt(p.marca_avg, 2)} | AS {_fmt(p.as_avg, 2)} | "
                f"consistencia {_fmt(p.consistency, 2)}\n"
                f"  Valor manual {_fmt(p.manual_value)} | nota: {p.note or '-'} | "
                f"tags: {', '.join(p.tags) or '-'}\n"
                f"  Flags: pico={p.is_peak_year} banquillo={p.is_bench_risk} "
                f"penaltis={p.is_penalty_taker} nuevo={p.is_new} fichado={p.is_drafted} "
                f"cambio_equipo={p.team_changed}"
            )
        return "\n\n".join(out)

    async def estado_draft() -> str:
        draft = await ctx.draft()
        total = len(draft.picks)
        by_id = {p.participant_id: p for p in draft.participants}
        turn = "draft no iniciado o terminado"
        if draft.next_participant_id is not None:
            p = by_id.get(draft.next_participant_id)
            if p is not None:
                turn = ctx.participant_label(p.participant_id, p.display_name)
        recent = draft.picks[-10:]
        lines = [
            f"Draft {draft.phase} ({draft.draft_type}), estado {draft.status}.",
            f"{total} picks hechos. Siguiente pick: #{total + 1}, le toca a {turn}.",
            f"{len(draft.participants)} participantes.",
        ]
        if recent:
            lines.append("Ultimos picks:")
            for pick in recent:
                who = ctx.participant_label(pick.participant_id, pick.display_name)
                lines.append(
                    f"  #{pick.pick_number} (ronda {pick.round_number}) {who} -> "
                    f"{pick.player_name} ({pick.position}, {pick.team_name})"
                )
        return "\n".join(lines)

    async def plantilla(participante: str | None = None) -> str:
        draft = await ctx.draft()
        target_id: int | None = None
        if participante:
            needle = participante.lower()
            for p in draft.participants:
                label = ctx.participant_label(p.participant_id, p.display_name).lower()
                if needle in label or needle in p.display_name.lower():
                    target_id = p.participant_id
                    break
            if target_id is None:
                return f"No encuentro al participante '{participante}'."
        else:
            target_id = draft.next_participant_id
            if target_id is None:
                return "No hay turno activo; indica un participante."

        owned = [pk for pk in draft.picks if pk.participant_id == target_id]
        counts = {pos: sum(1 for pk in owned if pk.position == pos) for pos in POSITIONS}
        who = next((p for p in draft.participants if p.participant_id == target_id), None)
        label = ctx.participant_label(target_id, who.display_name if who else str(target_id))

        lines = [f"Plantilla de {label}: {len(owned)} jugadores de 26."]
        for pos in POSITIONS:
            lines.append(f"  {pos}: {counts[pos]} (titulares necesarios: {STARTER_SLOTS[pos]})")
        if owned:
            lines.append("Jugadores:")
            for pk in owned:
                lines.append(f"  {pk.player_name} ({pk.position}, {pk.team_name})")
        return "\n".join(lines)

    async def escasez_posicional() -> str:
        board = await ctx.board()
        available = [p for p in board.players if not p.is_drafted]
        lines = ["Escasez AHORA MISMO entre los disponibles (Prioridad y VORP del tablero):"]
        for pos in POSITIONS:
            rows = sorted(
                (p for p in available if p.position == pos),
                key=lambda p: p.priority or -1e9,
                reverse=True,
            )
            if not rows:
                lines.append(f"  {pos}: sin disponibles.")
                continue
            best = rows[0]
            third = rows[2] if len(rows) > 2 else None
            over_replacement = sum(1 for p in rows if (p.vorp or 0) > 0)
            drop = (
                _fmt((best.priority or 0) - (third.priority or 0))
                if third and best.priority is not None
                else "-"
            )
            lines.append(
                f"  {pos}: mejor {best.display_name} (Prio {_fmt(best.priority)}, "
                f"VORP {_fmt(best.vorp, 2)}); caida al 3o: {drop}; "
                f"{over_replacement} por encima del reemplazo; {len(rows)} disponibles."
            )
        return "\n".join(lines)

    async def escasez_historica() -> str:
        return HISTORICAL_SCARCITY

    return [
        ToolSpec(
            name="buscar_jugadores",
            description=(
                "Busca jugadores en el tablero de draft de la temporada en curso, con sus "
                "metricas (Prioridad, Base, VORP, Salto, Tier, Disponibilidad, tags y flags). "
                "Llamala SIEMPRE que la pregunta mencione jugadores, posiciones o equipos "
                "concretos, o pida comparar o listar opciones."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "posicion": {
                        "type": "string",
                        "enum": list(POSITIONS),
                        "description": "Filtra por posicion. Omitir para todas.",
                    },
                    "equipo": {
                        "type": "string",
                        "description": "Filtra por equipo de La Liga (coincidencia parcial).",
                    },
                    "solo_disponibles": {
                        "type": "boolean",
                        "description": "Si true (por defecto), excluye los ya fichados.",
                    },
                    "orden": {
                        "type": "string",
                        "enum": ["prioridad", "vorp"],
                        "description": "Criterio de orden. Prioridad es el orden maestro.",
                    },
                    "limite": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "description": "Cuantos devolver (maximo 50).",
                    },
                },
                "required": [],
            },
            handler=buscar_jugadores,
        ),
        ToolSpec(
            name="detalle_jugador",
            description=(
                "Ficha completa de un jugador por nombre: todas sus metricas del tablero, "
                "historico, notas Marca/AS y flags. Llamala cuando pregunten por un jugador "
                "concreto o pidan justificar por que esta donde esta."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "nombre": {
                        "type": "string",
                        "description": "Nombre o parte del nombre del jugador.",
                    }
                },
                "required": ["nombre"],
            },
            handler=detalle_jugador,
        ),
        ToolSpec(
            name="estado_draft",
            description=(
                "Estado del draft en vivo: picks hechos, numero del siguiente pick, a quien le "
                "toca y los ultimos picks. Llamala cuando la pregunta dependa del momento del "
                "draft ('a quien cojo ahora', 'que queda', 'cuando me toca')."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=estado_draft,
        ),
        ToolSpec(
            name="plantilla",
            description=(
                "Plantilla actual de un participante con el reparto por posicion frente a las "
                "plazas de titular. Sin argumento, la del que tiene el turno. Llamala antes de "
                "recomendar un pick, para no repetir posicion ya cubierta."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "participante": {
                        "type": "string",
                        "description": "Nombre o etiqueta del participante. Omitir para el del turno.",
                    }
                },
                "required": [],
            },
            handler=plantilla,
        ),
        ToolSpec(
            name="escasez_posicional",
            description=(
                "Escasez por posicion AHORA, calculada sobre los jugadores aun disponibles: "
                "mejor de cada posicion, caida al tercero y cuantos superan el nivel de "
                "reemplazo. Llamala para decidir que posicion atacar en este pick."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=escasez_posicional,
        ),
        ToolSpec(
            name="escasez_historica",
            description=(
                "Escasez posicional medida sobre 8 temporadas reales de esta liga: cuanto vale "
                "el mejor de cada posicion sobre su reemplazo y cuanto cuesta esperar. Llamala "
                "para preguntas de estrategia general ('conviene portero pronto?')."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=escasez_historica,
        ),
    ]
