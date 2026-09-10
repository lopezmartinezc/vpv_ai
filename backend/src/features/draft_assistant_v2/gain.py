"""Deterministic improvement to today's best XI, not a forecast of lineup choices."""

from src.features.stats.schemas_draft import DraftValuePlayer

from .snapshot import Formation, Snapshot


def best_line(players: list[DraftValuePlayer], position: str, count: int) -> float:
    values = sorted(
        (p.priority for p in players if p.position == position and p.priority is not None),
        reverse=True,
    )
    return sum(values[:count])


def best_xi(players: list[DraftValuePlayer], formations: list[Formation]) -> float:
    keeper = best_line(players, "POR", 1)
    return max(
        (
            keeper
            + best_line(players, "DEF", f.defenders)
            + best_line(players, "MED", f.midfielders)
            + best_line(players, "DEL", f.forwards)
            for f in formations
        ),
        default=keeper,
    )


def roster_gain(snapshot: Snapshot, target: int | None, player: DraftValuePlayer) -> float | None:
    if target is None or not snapshot.formations or player.priority is None:
        return None
    owned = {p.id for p in snapshot.roster if p.owner_id == target}
    if player.player_id in owned:
        return 0.0
    roster = [p for p in snapshot.players if p.player_id in owned]
    before = best_xi(roster, snapshot.formations)
    return max(0.0, round(best_xi([*roster, player], snapshot.formations) - before, 1))
