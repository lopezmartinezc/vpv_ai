"""A proposal of the chat as an eleven the screen can apply.

Built on the server from the asker's own squad and the valid formations: the
model names who enters and who leaves, the server works out the resulting
eleven and refuses what the rules would refuse. Nothing here saves anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.features.lineup_assistant.optimizer import Formation, Suggestion

_ORDER = {"POR": 0, "DEF": 1, "MED": 2, "DEL": 3}


class ProposalError(Exception):
    """Why the eleven cannot be formed, in words for the model."""


@dataclass(frozen=True)
class ProposedPlayer:
    player_id: int
    name: str
    position: str


@dataclass(frozen=True)
class Proposal:
    formation: str
    players: list[ProposedPlayer]
    # Names, against the eleven the proposal started from.
    entering: list[str]
    leaving: list[str]
    basis: str

    def payload(self) -> dict[str, object]:
        return {
            "formation": self.formation,
            "players": [
                {"player_id": p.player_id, "name": p.name, "position": p.position}
                for p in self.players
            ],
            "entering": self.entering,
            "leaving": self.leaving,
            "basis": self.basis,
        }


def _formation_of(positions: Sequence[str], formations: Sequence[Formation]) -> str:
    counts = {pos: positions.count(pos) for pos in _ORDER}
    if counts["POR"] != 1:
        raise ProposalError(f"Hacen falta exactamente 1 portero y hay {counts['POR']}.")
    for f in formations:
        if (f.defenders, f.midfielders, f.forwards) == (
            counts["DEF"],
            counts["MED"],
            counts["DEL"],
        ):
            return f.name
    raise ProposalError(
        f"{counts['DEF']} DEF, {counts['MED']} MED y {counts['DEL']} DEL no es ninguna "
        f"formacion valida ({', '.join(f.name for f in formations)})."
    )


def _finish(
    base_ids: Sequence[int],
    result_ids: Sequence[int],
    squad: Sequence,
    formations: Sequence[Formation],
    basis: str,
) -> Proposal:
    by_id = {p.player_id: p for p in squad}
    if len(result_ids) < 11:
        raise ProposalError(
            f"Con eso hay {len(result_ids)} jugadores: faltan {11 - len(result_ids)}."
        )
    if len(result_ids) > 11:
        raise ProposalError(
            f"Con eso hay {len(result_ids)} jugadores: sobran {len(result_ids) - 11}."
        )
    players = sorted(
        (ProposedPlayer(i, by_id[i].display_name, by_id[i].position) for i in result_ids),
        key=lambda p: (_ORDER.get(p.position, 9), p.name),
    )
    formation = _formation_of([p.position for p in players], formations)
    base, result = set(base_ids), set(result_ids)
    return Proposal(
        formation=formation,
        players=players,
        entering=sorted(by_id[i].display_name for i in result - base),
        leaving=sorted(by_id[i].display_name for i in base - result if i in by_id),
        basis=basis,
    )


def swap(
    base_ids: Sequence[int],
    *,
    entering: Sequence[int],
    leaving: Sequence[int],
    squad: Sequence,
    formations: Sequence[Formation],
    basis: str,
) -> Proposal:
    """The eleven after ``leaving`` go out and ``entering`` come in."""
    by_id = {p.player_id: p for p in squad}
    strangers = [i for i in entering if i not in by_id]
    if strangers:
        raise ProposalError(f"No estan en tu plantilla: {strangers}.")
    for i in leaving:
        if i not in base_ids:
            raise ProposalError(
                f"{by_id[i].display_name if i in by_id else i} no esta en el once."
            )
    for i in entering:
        if i in base_ids and i not in leaving:
            raise ProposalError(f"{by_id[i].display_name} ya esta en el once.")
    result = [i for i in base_ids if i not in set(leaving)]
    result += [i for i in entering if i not in result]
    return _finish(base_ids, result, squad, formations, basis)


def from_suggestion(suggestion: Suggestion, base_ids: Sequence[int], squad: Sequence) -> Proposal:
    """The optimizer's eleven, as a proposal against what is on screen."""
    by_id = {p.player_id: p for p in squad}
    ids = [v.candidate.player_id for v in suggestion.eleven]
    players = sorted(
        (ProposedPlayer(i, by_id[i].display_name, by_id[i].position) for i in ids),
        key=lambda p: (_ORDER.get(p.position, 9), p.name),
    )
    base, result = set(base_ids), set(ids)
    return Proposal(
        formation=suggestion.formation,
        players=players,
        entering=sorted(by_id[i].display_name for i in result - base),
        leaving=sorted(by_id[i].display_name for i in base - result if i in by_id),
        basis=f"Once de mas valor esperado: {suggestion.total:.1f} puntos.",
    )
