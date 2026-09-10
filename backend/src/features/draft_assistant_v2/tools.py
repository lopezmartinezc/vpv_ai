from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import Field, ValidationError

from .evaluation import formation_needs, rivals_before_turn, sorted_players, turn_context
from .gain import roster_gain
from .schemas import PositiveId, StrictModel, ViewContext
from .snapshot import Snapshot
from .supplemental import ExtraQuery, extra_query


class Empty(StrictModel):
    pass


class Search(ViewContext):
    limit: Annotated[int, Field(strict=True, ge=1, le=30)] = 10


class Detail(StrictModel):
    player_id: PositiveId


class Final(StrictModel):
    explanation: str = Field(min_length=1, max_length=8000)
    player_ids: list[PositiveId] = Field(default_factory=list, max_length=3)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


SCHEMAS: dict[str, type[StrictModel]] = {
    "calendario": ExtraQuery,
    "rendimiento_temporada": ExtraQuery,
    "estado_draft": Empty,
    "buscar_jugadores": Search,
    "detalle_jugador": Detail,
    "evaluar_pick": Empty,
    "plantillas": Empty,
    "responder": Final,
}
DESCRIPTIONS = {
    "calendario": "Partidos cargados, por equipo y jornada; dificultad específica de posición.",
    "rendimiento_temporada": "Rendimiento observado de la temporada; incluye pre-draft y número de partidos.",
    "estado_draft": "Estado, turnos y participante consultado; no implica disponibilidad futura.",
    "buscar_jugadores": "Jugadores disponibles, ordenados por métricas del servidor. Filtros opcionales.",
    "detalle_jugador": "Métricas y observaciones de un jugador por ID, incluidas sus incertidumbres.",
    "evaluar_pick": "Candidatos y alternativas del contexto visible, necesidades y espera real.",
    "plantillas": "Propiedad vigente de todos los participantes, también en invierno.",
    "responder": "Termina con explicación, hasta tres IDs consultados y referencias de evidencia.",
}


# How many of the latest picks `estado_draft` spells out. Enough to see what the
# rivals just did; the full history lives in `plantillas`.
RECENT_PICKS = 12


def explain(exc: Exception) -> str:
    """What was wrong with a tool call, in terms the model can act on.

    A limit out of range, an unknown field, an explanation over the cap and an
    evidence id that was never consulted all need different corrections; one
    generic line for all of them leaves the model retrying blind. Bounded, and
    never echoing the offending input back.
    """
    if isinstance(exc, ValidationError):
        parts = [
            f"{'.'.join(str(x) for x in e['loc']) or 'argumentos'}: {e['msg']}"
            for e in exc.errors()[:5]
        ]
        return "; ".join(parts)[:600]
    if isinstance(exc, KeyError):
        return "Herramienta desconocida."
    return str(exc)[:600] or "Argumentos inválidos."


class ToolResult(StrictModel):
    content: str
    final: Final | None = None
    error: bool = False


class Toolset:
    def __init__(self, snapshot: Snapshot, user_id: int, view: ViewContext) -> None:
        snapshot.validate_view(view)
        self.snapshot = snapshot
        self.view = view
        self.target = snapshot.target(user_id, view)
        self.view = view.model_copy(update={"participant_id": self.target})
        self.seen: set[int] = set()
        self.evidence: set[str] = set()

    def register(self, key: str, content: str) -> str:
        self.evidence.add(key)
        return json.dumps({"evidence_id": key, "data": json.loads(content)}, ensure_ascii=False)

    def player(self, player_id: int) -> str:
        player = next((p for p in self.snapshot.players if p.player_id == player_id), None)
        if player is None:
            raise ValueError("Jugador sin datos en este tablero.")
        self.seen.add(player_id)
        card = self.snapshot.card(player)
        card.marginal_gain = roster_gain(self.snapshot, self.target, player)
        return self.register(f"player:{player_id}", card.model_dump_json())

    def state(self) -> str:
        picks = self.snapshot.draft.picks
        data = {
            "draft_id": self.snapshot.draft.id,
            "phase": self.snapshot.draft.phase,
            "participant": self.target,
            "turn": turn_context(self.snapshot, self.target),
            "pool_size": self.snapshot.pool_size,
            # Hashes and pick count only. The capture time would make every
            # bootstrap unique and defeat prefix caching across questions.
            "revision": self.snapshot.revision().model_dump(exclude={"at"}),
            "selected_player_ids": self.view.selected_player_ids,
            # Summarised, not listed: every pick by name is 286 rows by the end
            # of a draft, resent on every round, and `plantillas` already
            # answers "who has whom". What the model needs from here is where
            # the draft stands and what has just happened.
            "total_picks": len(picks),
            "current_round": len(picks) // max(1, len(self.snapshot.draft.participants)) + 1,
            "picks_by_participant": {
                str(p.participant_id): sum(x.participant_id == p.participant_id for x in picks)
                for p in self.snapshot.draft.participants
            },
            "recent_picks": [
                {
                    "number": p.pick_number,
                    "round": p.round_number,
                    "player_id": p.player_id,
                    "player": p.player_name,
                    "position": p.position,
                    "team": p.team_name,
                    "participant_id": p.participant_id,
                }
                for p in picks[-RECENT_PICKS:]
            ],
            "note": "Si participant es null, pide elegir plantilla; no uses la del turno.",
        }
        return self.register("state", json.dumps(data))

    def search(self, args: Search) -> str:
        args = args.model_copy(update={"participant_id": self.target})
        rows = sorted_players(self.snapshot, args)[: args.limit]
        return "[" + ",".join(self.player(p.player_id) for p in rows) + "]"

    def detail(self, player_id: int) -> str:
        card = self.player(player_id)
        player = next(p for p in self.snapshot.players if p.player_id == player_id)
        # Notes are bounded, untrusted data, never instructions. No participant names.
        detail = player.model_dump(exclude={"note", "photo_path", "slug"})
        detail["untrusted_note"] = (player.note or "")[:1000]
        return json.dumps({"card": json.loads(card), "metrics": detail}, ensure_ascii=False)

    def rosters(self) -> str:
        data = [
            {
                "participant_id": p.participant_id,
                "players": [
                    r.model_dump() for r in self.snapshot.roster if r.owner_id == p.participant_id
                ],
                "missing_by_formation": formation_needs(self.snapshot, p.participant_id),
            }
            for p in self.snapshot.draft.participants
        ]
        return self.register("rosters", json.dumps(data, ensure_ascii=False))

    def evaluate(self) -> str:
        ranked = sorted_players(self.snapshot, self.view)
        ids = list(
            dict.fromkeys([*self.view.selected_player_ids, *(p.player_id for p in ranked[:8])])
        )
        cards = [json.loads(self.player(pid)) for pid in ids]
        data = {
            "context": self.view.model_dump(),
            "candidates": cards,
            "missing_by_formation": formation_needs(self.snapshot, self.target),
            "turn": turn_context(self.snapshot, self.target),
            "rivals_before_following_turn": rivals_before_turn(self.snapshot, self.target),
            "uncertainties": [
                "No hay probabilidades calibradas de que un jugador siga libre.",
                "Las proyecciones no son puntos garantizados.",
                "Objetivo/evitar son preferencias; event_share es composición.",
            ],
        }
        return self.register("evaluation", json.dumps(data, ensure_ascii=False))

    def finish(self, args: Final) -> ToolResult:
        if not set(args.player_ids) <= self.seen or not set(args.evidence_ids) <= self.evidence:
            raise ValueError("Solo puedes citar jugadores y evidencia consultados.")
        return ToolResult(content="Respuesta validada.", final=args)

    async def call(self, name: str, raw: str) -> ToolResult:
        if name not in ("calendario", "rendimiento_temporada"):
            return self.dispatch(name, raw)
        try:
            args = ExtraQuery.model_validate_json(raw)
            result = await extra_query(self.snapshot.draft.season_id, name, args)
            return ToolResult(content=self.register(name, result))
        except (ValidationError, ValueError) as exc:
            return ToolResult(error=True, content=f"INVALID_TOOL_ARGUMENTS: {explain(exc)}")

    def dispatch(self, name: str, raw: str) -> ToolResult:
        try:
            schema = SCHEMAS.get(name)
            if schema is None:
                raise ValueError("Herramienta desconocida.")
            args = schema.model_validate_json(raw)
            if isinstance(args, Final):
                return self.finish(args)
            if isinstance(args, Search):
                return ToolResult(content=self.search(args))
            if isinstance(args, Detail):
                return ToolResult(content=self.detail(args.player_id))
            handler = {
                "estado_draft": self.state,
                "evaluar_pick": self.evaluate,
                "plantillas": self.rosters,
            }[name]
            return ToolResult(content=handler())
        except (ValidationError, ValueError, KeyError) as exc:
            return ToolResult(
                error=True,
                content=json.dumps(
                    {"code": "INVALID_TOOL_ARGUMENTS", "message": explain(exc)},
                    ensure_ascii=False,
                ),
            )


def tool_definitions(provider: Literal["openai", "anthropic"]) -> str:
    definitions = []
    for name, schema in SCHEMAS.items():
        definition = {"name": name, "description": DESCRIPTIONS[name]}
        if provider == "openai":
            definitions.append(
                {
                    **definition,
                    "type": "function",
                    "strict": False,
                    "parameters": schema.model_json_schema(),
                }
            )
        else:
            definitions.append({**definition, "input_schema": schema.model_json_schema()})
    return json.dumps(definitions)
