from __future__ import annotations

from src.features.draft_assistant.turn_math import next_pick_for, upcoming_picks
from src.features.stats.schemas_draft import DraftValuePlayer

from .gain import roster_gain
from .schemas import ViewContext
from .snapshot import Snapshot


def ordered_participants(snapshot: Snapshot) -> list[int]:
    return [
        p.participant_id
        for p in sorted(
            snapshot.draft.participants,
            key=lambda p: (
                p.draft_order if p.draft_order is not None else 10**9,
                p.participant_id,
            ),
        )
    ]


def score(
    snapshot: Snapshot, view: ViewContext, player: DraftValuePlayer
) -> tuple[bool, float, int]:
    value = (
        roster_gain(snapshot, view.participant_id, player)
        if view.order == "gain"
        else (player.vorp if view.order == "vorp" else player.priority)
    )
    return value is not None, value if value is not None else 0.0, -player.player_id


def sorted_players(snapshot: Snapshot, view: ViewContext) -> list[DraftValuePlayer]:
    available = snapshot.available_ids()
    rows = [
        p
        for p in snapshot.players
        if p.player_id in available
        and (not view.position or p.position == view.position)
        and view.team.lower() in p.team_name.lower()
        and view.search.lower() in p.display_name.lower()
    ]
    return sorted(
        rows,
        key=lambda p: score(snapshot, view, p),
        reverse=True,
    )


def formation_needs(snapshot: Snapshot, participant_id: int | None) -> dict[str, dict[str, int]]:
    if participant_id is None:
        return {}
    owned = [p for p in snapshot.roster if p.owner_id == participant_id]
    counts = {pos: sum(p.position == pos for p in owned) for pos in ("POR", "DEF", "MED", "DEL")}
    return {
        f.name: {
            pos: max(0, required - counts[pos])
            for pos, required in {
                "POR": 1,
                "DEF": f.defenders,
                "MED": f.midfielders,
                "DEL": f.forwards,
            }.items()
        }
        for f in snapshot.formations
    }


def turn_context(snapshot: Snapshot, target: int | None) -> dict[str, int | str | None]:
    draft = snapshot.draft
    result: dict[str, int | str | None] = {
        "status": draft.status,
        "next_pick": None,
        "following_pick": None,
        "picks_between": None,
    }
    if (
        target is None
        or draft.status in ("completed", "paused")
        or snapshot.season_status == "finished"
    ):
        return result
    ordered = ordered_participants(snapshot)
    start = max((p.pick_number for p in draft.picks), default=0) + 1
    end = len(ordered) * snapshot.pool_size if draft.phase == "preseason" else None
    mine = next_pick_for(target, start - 1, draft.draft_type, ordered) if target else None
    if mine is None or (end is not None and mine > end):
        return result
    following = next_pick_for(target, mine, draft.draft_type, ordered)
    if end is not None and following is not None and following > end:
        following = None
    result.update(
        next_pick=mine,
        following_pick=following,
        picks_between=following - mine - 1 if following else None,
    )
    return result


def rivals_before_turn(snapshot: Snapshot, target: int | None) -> list[int]:
    context = turn_context(snapshot, target)
    following = context["following_pick"]
    if not isinstance(following, int):
        return []
    start = max((p.pick_number for p in snapshot.draft.picks), default=0) + 1
    ordered = [
        p.participant_id
        for p in sorted(
            snapshot.draft.participants,
            key=lambda p: (
                p.draft_order if p.draft_order is not None else 10**9,
                p.participant_id,
            ),
        )
    ]
    picks = upcoming_picks(start, snapshot.draft.draft_type, ordered, following - start)
    return list(dict.fromkeys(p.participant_id for p in picks if p.participant_id != target))
