"""The eleven being edited, checked and put into words for the model.

The screen sends it with every question. It is the asker's own squad or
nothing: ids outside it, a player out of his position or repeated are
refused before anything reaches the model.
"""

from __future__ import annotations

from src.core.exceptions import BusinessRuleError
from src.features.lineup_assistant.schemas import LineupDraft
from src.features.lineups.schemas import MyLineupResponse

_ORDER = ("POR", "DEF", "MED", "DEL")


def validate_draft(draft: LineupDraft, mine: MyLineupResponse) -> None:
    positions = {p.player_id: p.position for p in mine.squad}
    ids = [s.player_id for s in draft.players]
    if len(ids) != len(set(ids)):
        raise BusinessRuleError("No se puede repetir jugador en el once en edicion")
    strangers = set(ids) - positions.keys()
    if strangers:
        raise BusinessRuleError(f"Jugadores no pertenecen a tu plantilla: {sorted(strangers)}")
    misplaced = {
        s.player_id: f"{s.position_slot} (es {positions[s.player_id]})"
        for s in draft.players
        if s.position_slot != positions[s.player_id]
    }
    if misplaced:
        raise BusinessRuleError(f"Jugadores fuera de su posicion: {misplaced}")


def draft_text(draft: LineupDraft, mine: MyLineupResponse) -> str:
    """What the model is told before the question. Validated draft only."""
    names = {p.player_id: p.display_name for p in mine.squad}
    by_pos: dict[str, list[str]] = {pos: [] for pos in _ORDER}
    for s in draft.players:
        by_pos[s.position_slot].append(names[s.player_id])
    formation = draft.formation or "sin formacion aun"
    lines = [
        f"ONCE EN EDICION (sin enviar): {formation}, {len(draft.players)} de 11.",
        *(f"- {pos}: {', '.join(by_pos[pos]) or '-'}" for pos in _ORDER),
    ]
    saved = mine.current_lineup
    if saved is None:
        lines.append("Todavia no hay once guardado.")
    else:
        saved_ids = {p.player_id for p in saved.players}
        draft_ids = {s.player_id for s in draft.players}
        entering = sorted(names[i] for i in draft_ids - saved_ids)
        leaving = sorted(names[i] for i in saved_ids - draft_ids if i in names)
        if not entering and not leaving:
            lines.append(f"Es igual que el once guardado ({saved.formation}).")
        else:
            changes = [*(f"entra {n}" for n in entering), *(f"sale {n}" for n in leaving)]
            lines.append(f"Respecto al once guardado ({saved.formation}): {'; '.join(changes)}.")
    return "\n".join(lines)
