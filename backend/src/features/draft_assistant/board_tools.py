"""The tools the draft assistant can call.

Every one of them reads through the services the UI already uses
(``DraftValueService``, ``DraftService``), so the chat and the board can never
disagree. None of them writes. None of them takes a season, draft or
participant id from the model — those come from the request context below.

Handlers return compact plain text rather than JSON: it costs roughly half the
tokens for the same information and the model reads it just as well.
"""

from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.draft_assistant.tools import ToolHandler, ToolSpec
from src.features.draft_assistant.turn_math import next_pick_for, upcoming_picks
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
defensa del equipo), lo que juega ligeramente a su favor frente a la tabla.

PUNTOS REALIZADOS EN LA PORTERIA (lo que de verdad se alineo, 8 temporadas):
- Con un portero top 1-3 en propiedad: 230. Top 4-6: 193. Top 7-11: 173.
  12o o peor: 142.
- Titular + su SUPLENTE (mismo equipo): 194 realizados, solo 13 pts perdidos por
  elegir mal la jornada. Dos titulares de equipos DISTINTOS: 172 realizados y 63
  perdidos por elegir mal. La opcionalidad de dos titulares es una trampa.
- Un portero top se pierde ~3 jornadas de 33; su suplente cubre justo esas.

CON 13 PARTICIPANTES:
- Solo hay 13-15 porteros que jueguen el 75%+ de la liga: uno por cabeza, sin
  margen. El 13o portero (reemplazo) vale 138; el 26o (ultimo draftado), 32.
- Excedente del pick de primera ronda: DEL 200, DEF 120, POR 118, MED 99.
- Cerrar el portero titular entre la ronda 5 y la 7; su suplente en las ultimas.

DRAFT REAL DEL AÑO PASADO (11 participantes), por ronda:
  R1: 6 DEL, 3 MED, 0 DEF, 2 POR (picks 4 y 6) - 90% de Madrid/Barca/Atletico
  R2: 3 DEL, 3 MED, 4 DEF, 1 POR (pick 18)      - 81%
  R3: 3 DEL, 4 MED, 3 DEF, 1 POR (pick 25)      - 54%
  R4: 7 DEL, 4 MED, 0 DEF, 0 POR                - 27%
Nadie coge defensas en la primera ronda; el tiron del equipo grande se desploma a
partir de la tercera.

FORMA PRE-DRAFT (lo visible al elegir) vs RESULTADO FINAL, top-3 por posicion:
  POR: 172 pts finales, 58% acaban top-6 (la posicion mas predecible)
  DEL: 227 pts finales, 46% acaban top-6, cuartil bajo 186, peor caso 83
  DEF/MED: ~160 pts finales, 17% acaban top-6
El delantero identificable en el draft gana al portero en media, en cuartil bajo
y en peor caso (el del portero es 14). La "seguridad" del portero no esta en los
datos: la seguridad real es tener UN titular claro y no tener que elegir."""


# The board aggregates every player_stats row of the last N seasons (~400ms of
# SQL plus the projection in Python), and none of that changes while a draft is
# running — only who owns whom, which is read fresh from the picks below. So it
# is cached briefly across requests to keep follow-up questions snappy.
#
# The staleness that IS possible: an admin tag or manual value edited on the
# board takes up to BOARD_TTL_SECONDS to reach the assistant.
_BOARD_CACHE: dict[int, tuple[float, DraftValueResponse]] = {}
BOARD_TTL_SECONDS = 60.0


@dataclass
class AssistantContext:
    """Everything the tools are allowed to touch, fixed by the caller.

    The model can influence the arguments of a tool, never these.
    """

    session: AsyncSession
    season_id: int
    phase: str
    # Who is asking, from the JWT. Never from the model: it decides what to ask,
    # never on whose behalf.
    user_id: int = 0
    anonymize_participants: bool = True
    _draft: DraftDetailResponse | None = field(default=None, init=False, repr=False)
    _picked: set[int] | None = field(default=None, init=False, repr=False)

    async def board(self) -> DraftValueResponse:
        now = time.monotonic()
        cached = _BOARD_CACHE.get(self.season_id)
        if cached is not None and now - cached[0] < BOARD_TTL_SECONDS:
            return cached[1]
        board = await DraftValueService(self.session).get_draft_values(self.season_id)
        _BOARD_CACHE[self.season_id] = (now, board)
        return board

    async def draft(self) -> DraftDetailResponse:
        if self._draft is None:
            self._draft = await DraftService(self.session).get_draft_detail(
                self.season_id, self.phase
            )
        return self._draft

    async def picked_ids(self) -> set[int]:
        """Players already taken, read from the live picks.

        Deliberately NOT ``DraftValuePlayer.is_drafted``: that flag rides along
        with the cached board and would go stale exactly when it matters most —
        the assistant would keep recommending a player somebody just took.
        """
        if self._picked is None:
            draft = await self.draft()
            self._picked = {pk.player_id for pk in draft.picks}
        return self._picked

    async def caller_participant_id(self) -> int | None:
        """The asker's participant row in this draft, or None if they only run it.

        Without this, "de que voy corto?" answers about whoever holds the turn —
        the same words, a different squad, and nothing on screen saying so.
        """
        draft = await self.draft()
        return next(
            (p.participant_id for p in draft.participants if p.user_id == self.user_id),
            None,
        )

    def participant_label(self, participant_id: int, display_name: str) -> str:
        """Names of other people are not needed for the reasoning, so by default
        they do not leave the server. Set ASSISTANT_ANONYMIZE_PARTICIPANTS=false
        to send real names instead."""
        if not self.anonymize_participants:
            return display_name
        return f"Participante {participant_id}"

    def ordered_participant_ids(self, draft: DraftDetailResponse) -> list[int]:
        """Draft order, with the same deterministic tiebreak the draft itself
        uses — id — so a missing or duplicated draft_order cannot make the
        assistant project a different order than the board shows."""
        return [
            p.participant_id
            for p in sorted(
                draft.participants,
                key=lambda x: (
                    x.draft_order if x.draft_order is not None else 10**9,
                    x.participant_id,
                ),
            )
        ]


def _fmt(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _player_row(p: DraftValuePlayer, drafted: bool) -> str:
    flags = []
    if drafted:
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


def _guarded(ctx: AssistantContext, fn: ToolHandler) -> ToolHandler:
    """Roll the DB session back if a tool blows up.

    A failed query leaves the transaction aborted, so without this the FIRST
    failure poisons every later tool: the model burns its whole round budget on
    errors and answers nothing. Rolling back is safe here because these tools
    only read.
    """

    async def wrapped(**kwargs: Any) -> str:
        try:
            return await fn(**kwargs)
        except Exception:
            with suppress(Exception):
                await ctx.session.rollback()
            raise

    return wrapped


def build_tools(ctx: AssistantContext) -> list[ToolSpec]:
    def _find_participant(draft: DraftDetailResponse, needle: str) -> int | None:
        """Resolve a participant by whatever the model was shown.

        With anonymisation on, the model only ever sees "Participante 7", so it
        can only ask by that; with it off it sees real names. Matching both means
        the tool works either way without the model knowing which mode is on.
        """
        want = needle.lower().strip()
        for p in draft.participants:
            label = ctx.participant_label(p.participant_id, p.display_name).lower()
            if want in label or want in p.display_name.lower():
                return p.participant_id
        return None

    async def buscar_jugadores(
        posicion: str | None = None,
        equipo: str | None = None,
        solo_disponibles: bool = True,
        orden: str = "prioridad",
        limite: int = 20,
    ) -> str:
        board = await ctx.board()
        picked = await ctx.picked_ids()
        rows = list(board.players)
        if posicion:
            rows = [p for p in rows if p.position == posicion.upper()]
        if equipo:
            needle = equipo.lower()
            rows = [p for p in rows if needle in p.team_name.lower()]
        if solo_disponibles:
            rows = [p for p in rows if p.player_id not in picked]

        key = (lambda p: p.vorp or -1e9) if orden == "vorp" else (lambda p: p.priority or -1e9)
        rows.sort(key=key, reverse=True)
        rows = rows[:limite]

        if not rows:
            return "Sin resultados con esos filtros."
        header = f"{len(rows)} jugadores (orden: {orden}):"
        return header + "\n" + "\n".join(_player_row(p, p.player_id in picked) for p in rows)

    async def detalle_jugador(nombre: str) -> str:
        board = await ctx.board()
        picked = await ctx.picked_ids()
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
                f"penaltis={p.is_penalty_taker} nuevo={p.is_new} "
                f"fichado={p.player_id in picked} cambio_equipo={p.team_changed}"
            )
        return "\n\n".join(out)

    async def estado_draft() -> str:
        draft = await ctx.draft()
        total = len(draft.picks)
        by_id = {p.participant_id: p for p in draft.participants}
        n = len(draft.participants)
        turn = "draft no iniciado o terminado"
        if draft.next_participant_id is not None:
            p = by_id.get(draft.next_participant_id)
            if p is not None:
                turn = ctx.participant_label(p.participant_id, p.display_name)
        caller_id = await ctx.caller_participant_id()
        if caller_id is None:
            who = "Quien pregunta no participa en este draft (solo lo administra)."
        else:
            me = by_id.get(caller_id)
            label = ctx.participant_label(caller_id, me.display_name if me else str(caller_id))
            mine = caller_id == draft.next_participant_id
            who = f"Quien pregunta es {label}" + (
                " y ES SU TURNO ahora." if mine else " y NO es su turno ahora."
            )

        lines = [
            f"Draft {draft.phase} ({draft.draft_type}), estado {draft.status}.",
            f"{n} participantes, {total} picks hechos.",
            f"Siguiente pick: #{total + 1}"
            + (f" (ronda {total // n + 1})" if n else "")
            + f", le toca a {turn}.",
            who,
        ]
        recent = draft.picks[-10:]
        if recent:
            lines.append(f"Ultimos {len(recent)} picks (usa picks_realizados para el resto):")
            for pick in recent:
                who = ctx.participant_label(pick.participant_id, pick.display_name)
                lines.append(
                    f"  #{pick.pick_number} (R{pick.round_number}) {who} -> "
                    f"{pick.player_name} ({pick.position}, {pick.team_name})"
                )
        return "\n".join(lines)

    async def picks_realizados(
        participante: str | None = None,
        posicion: str | None = None,
        equipo: str | None = None,
        ronda: int | None = None,
        limite: int = 40,
    ) -> str:
        draft = await ctx.draft()
        rows = list(draft.picks)
        if participante:
            target = _find_participant(draft, participante)
            if target is None:
                return f"No encuentro al participante '{participante}'."
            rows = [pk for pk in rows if pk.participant_id == target]
        if posicion:
            rows = [pk for pk in rows if pk.position == posicion.upper()]
        if equipo:
            needle = equipo.lower()
            rows = [pk for pk in rows if needle in (pk.team_name or "").lower()]
        if ronda is not None:
            rows = [pk for pk in rows if pk.round_number == ronda]

        total = len(rows)
        if total == 0:
            return "Ningun pick coincide con esos filtros."
        # Most recent first: mid-draft the question is almost always "what just
        # went", not "what went in round 1".
        rows = sorted(rows, key=lambda pk: pk.pick_number, reverse=True)[:limite]
        header = f"{total} picks coinciden" + (
            f", mostrando {len(rows)}" if total > len(rows) else ""
        )
        lines = [header + " (mas reciente primero):"]
        for pk in rows:
            who = ctx.participant_label(pk.participant_id, pk.display_name)
            dropped = f" (suelta a {pk.dropped_player_name})" if pk.dropped_player_name else ""
            lines.append(
                f"  #{pk.pick_number} (R{pk.round_number}) {who} -> "
                f"{pk.player_name} ({pk.position}, {pk.team_name}){dropped}"
            )
        return "\n".join(lines)

    async def proximos_turnos(cuantos: int = 12) -> str:
        """Who picks next, and how long each participant waits for their turn."""
        draft = await ctx.draft()
        ordered = ctx.ordered_participant_ids(draft)
        if not ordered:
            return "El draft no tiene participantes con orden asignado."
        next_pick = len(draft.picks) + 1
        by_id = {p.participant_id: p for p in draft.participants}

        def label(pid: int) -> str:
            p = by_id.get(pid)
            return ctx.participant_label(pid, p.display_name if p else str(pid))

        lines = [
            f"Tipo de draft: {draft.draft_type} "
            f"({'serpiente: las rondas pares van al reves' if draft.draft_type == 'snake' else 'lineal: todas las rondas en el mismo orden'})."
        ]
        upcoming = upcoming_picks(next_pick, draft.draft_type, ordered, cuantos)
        lines.append(f"Proximos {len(upcoming)} picks:")
        for i, up in enumerate(upcoming):
            marker = "  <- AHORA" if i == 0 else ""
            lines.append(
                f"  #{up.pick_number} (R{up.round_number}) {label(up.participant_id)}{marker}"
            )

        lines.append("Cuanto espera cada uno hasta su siguiente turno:")
        for pid in ordered:
            mine = next(
                (u.pick_number for u in upcoming if u.participant_id == pid),
                next_pick_for(pid, next_pick - 1, draft.draft_type, ordered),
            )
            if mine is None:
                continue
            following = next_pick_for(pid, mine, draft.draft_type, ordered)
            gap = (
                f", y luego el #{following} ({following - mine - 1} picks de espera)"
                if following
                else ""
            )
            lines.append(f"  {label(pid)}: elige en el #{mine}{gap}")
        return "\n".join(lines)

    async def plantillas_todas() -> str:
        """Every participant's shape at once — who is short of what."""
        draft = await ctx.draft()
        lines = [
            "Reparto por participante (POR/DEF/MED/DEL = total). "
            "Plazas de titular: POR 1, DEF 4, MED 3, DEL 3."
        ]
        for p in draft.participants:
            owned = [pk for pk in draft.picks if pk.participant_id == p.participant_id]
            counts = {pos: sum(1 for pk in owned if pk.position == pos) for pos in POSITIONS}
            short = [pos for pos in POSITIONS if counts[pos] < STARTER_SLOTS[pos]]
            gap = f"  <- sin cubrir titulares en {', '.join(short)}" if short else ""
            lines.append(
                f"  {ctx.participant_label(p.participant_id, p.display_name)}: "
                + "/".join(str(counts[pos]) for pos in POSITIONS)
                + f" = {len(owned)} de 26{gap}"
            )
        return "\n".join(lines)

    async def plantilla(participante: str | None = None) -> str:
        draft = await ctx.draft()
        target_id: int | None = None
        if participante:
            target_id = _find_participant(draft, participante)
            if target_id is None:
                return f"No encuentro al participante '{participante}'."
        else:
            # "Mi plantilla" means the ASKER's, not the turn holder's. Falling
            # back to the turn only when the asker does not play at all.
            target_id = await ctx.caller_participant_id() or draft.next_participant_id
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
        picked = await ctx.picked_ids()
        available = [p for p in board.players if p.player_id not in picked]
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
            handler=_guarded(ctx, buscar_jugadores),
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
            handler=_guarded(ctx, detalle_jugador),
        ),
        ToolSpec(
            name="estado_draft",
            description=(
                "Estado del draft en vivo: picks hechos, numero del siguiente pick, a quien le "
                "toca, los ultimos picks y QUIEN TE ESTA PREGUNTANDO (y si es su turno). "
                "Llamala cuando la pregunta dependa del momento del draft ('a quien cojo ahora', "
                "'que queda', 'cuando me toca') o de quien habla contigo ('yo', 'mi plantilla')."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_guarded(ctx, estado_draft),
        ),
        ToolSpec(
            name="picks_realizados",
            description=(
                "Consulta el historico COMPLETO de picks del draft, filtrable por participante, "
                "posicion, equipo o ronda. Llamala cuando pregunten que se ha fichado ya, quien "
                "cogio a alguien, cuantos de un equipo han salido, o que paso en una ronda. "
                "estado_draft solo enseña los 10 ultimos; para el resto usa esta."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "participante": {
                        "type": "string",
                        "description": "Nombre o etiqueta del participante. Omitir para todos.",
                    },
                    "posicion": {"type": "string", "enum": list(POSITIONS)},
                    "equipo": {
                        "type": "string",
                        "description": "Equipo de La Liga (coincidencia parcial).",
                    },
                    "ronda": {"type": "integer", "minimum": 1, "maximum": 30},
                    "limite": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": [],
            },
            handler=_guarded(ctx, picks_realizados),
        ),
        ToolSpec(
            name="proximos_turnos",
            description=(
                "Orden de los proximos picks y, para cada participante, en que pick elige y "
                "cuantos picks espera hasta el siguiente. Llamala SIEMPRE que la pregunta sea "
                "si conviene esperar a un jugador, a quien le toca, cuanto falta para volver a "
                "elegir, o quien queda por elegir en esta ronda. En draft serpiente la espera "
                "es muy desigual: en el giro se elige dos veces seguidas."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "cuantos": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 60,
                        "description": "Cuantos picks futuros listar (por defecto 12).",
                    }
                },
                "required": [],
            },
            handler=_guarded(ctx, proximos_turnos),
        ),
        ToolSpec(
            name="plantillas_todas",
            description=(
                "Reparto por posicion de TODOS los participantes de un vistazo, señalando a "
                "quien le faltan titulares. Llamala para ver quien va corto de que, o para "
                "anticipar que posicion van a atacar los demas antes de tu proximo turno."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_guarded(ctx, plantillas_todas),
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
                        "description": (
                            "Nombre o etiqueta del participante. OMITIR para la plantilla de "
                            "quien te esta preguntando (lo que quiere decir con 'mi plantilla' "
                            "o 'de que voy corto')."
                        ),
                    }
                },
                "required": [],
            },
            handler=_guarded(ctx, plantilla),
        ),
        ToolSpec(
            name="escasez_posicional",
            description=(
                "Escasez por posicion AHORA, calculada sobre los jugadores aun disponibles: "
                "mejor de cada posicion, caida al tercero y cuantos superan el nivel de "
                "reemplazo. Llamala para decidir que posicion atacar en este pick."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_guarded(ctx, escasez_posicional),
        ),
        ToolSpec(
            name="escasez_historica",
            description=(
                "Escasez posicional medida sobre 8 temporadas reales de esta liga: cuanto vale "
                "el mejor de cada posicion sobre su reemplazo y cuanto cuesta esperar. Llamala "
                "para preguntas de estrategia general ('conviene portero pronto?')."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_guarded(ctx, escasez_historica),
        ),
    ]
