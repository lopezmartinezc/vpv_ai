"""Re-sort draft picks within each round by participant's draft_order.

For preseason drafts: within each round, picks are sorted by draft_order
(snake reverses even rounds). This fixes historical drafts that may have
incorrect pick_number ordering.

Winter drafts are skipped (single round, no reordering needed).

Usage:
    cd backend
    PYTHONPATH=. python -m scripts.fix_draft_pick_order              # dry-run
    PYTHONPATH=. python -m scripts.fix_draft_pick_order --apply      # apply
    PYTHONPATH=. python -m scripts.fix_draft_pick_order --season 8   # specific season
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.features.drafts.repository import DraftRepository
from src.features.drafts.service import DraftService
from src.shared.models.draft import Draft


async def fix_drafts(apply: bool, season_id: int | None) -> None:
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Find all drafts
        stmt = select(Draft).order_by(Draft.id)
        if season_id:
            stmt = stmt.where(Draft.season_id == season_id)
        result = await session.execute(stmt)
        drafts = list(result.scalars().all())

        print(f"Found {len(drafts)} drafts")

        for draft in drafts:
            if draft.phase == "winter":
                print(f"  Draft {draft.id} (season {draft.season_id}, winter) — skipped")
                continue

            repo = DraftRepository(session)
            picks = await repo.get_picks(draft.id)
            participants = await repo.get_participants(draft.season_id)
            num_participants = len(participants)

            if num_participants == 0 or len(picks) == 0:
                print(f"  Draft {draft.id} (season {draft.season_id}, {draft.phase}) — no picks/participants")
                continue

            participant_order = {
                p.participant_id: (p.draft_order or 999) for p in participants
            }

            # Current pick order
            pick_ids = [p.id for p in picks]

            # Simulate the reorder logic
            pick_map = {p.id: p for p in picks}
            rounds: dict[int, list[int]] = {}
            for i, pick_id in enumerate(pick_ids):
                rnd = i // num_participants + 1
                rounds.setdefault(rnd, []).append(pick_id)

            new_entries: list[tuple[int, int, int]] = []
            pick_num = 1
            changes = 0

            for rnd in sorted(rounds):
                round_picks = rounds[rnd]
                reverse = draft.draft_type == "snake" and rnd % 2 == 0
                round_picks.sort(
                    key=lambda pid: participant_order.get(
                        pick_map[pid].participant_id, 999
                    ),
                    reverse=reverse,
                )
                for pid in round_picks:
                    old_pick = pick_map[pid]
                    if old_pick.pick_number != pick_num or old_pick.round_number != rnd:
                        changes += 1
                    new_entries.append((pid, pick_num, rnd))
                    pick_num += 1

            print(
                f"  Draft {draft.id} (season {draft.season_id}, {draft.phase}, "
                f"{draft.draft_type}) — {len(picks)} picks, {changes} changes needed"
            )

            if changes > 0 and apply:
                await repo.reorder_picks(draft.id, new_entries)
                await session.commit()
                print(f"    ✓ Applied {changes} changes")
            elif changes > 0:
                # Show a few examples
                for pid, new_num, new_rnd in new_entries[:5]:
                    old = pick_map[pid]
                    if old.pick_number != new_num or old.round_number != new_rnd:
                        print(
                            f"    {old.player_name} ({old.display_name}, order={old.draft_order}): "
                            f"pick #{old.pick_number} R{old.round_number} → "
                            f"pick #{new_num} R{new_rnd}"
                        )
                if changes > 5:
                    print(f"    ... and {changes - 5} more")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix draft pick ordering by draft_order")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--season", type=int, help="Only fix drafts for this season_id")
    args = parser.parse_args()

    if not args.apply:
        print("DRY RUN — use --apply to save changes\n")

    asyncio.run(fix_drafts(apply=args.apply, season_id=args.season))


if __name__ == "__main__":
    main()
