/**
 * Filtering the draft board by your own tags.
 *
 * Several tags read as OR, not AND: asking for "Objetivo, Duda" means show me
 * both lists, which is what you want when reviewing. Requiring a player to
 * carry every selected tag would almost always return nothing, since the tags
 * describe different things.
 *
 * The option that earns its place is UNTAGGED. Before a draft the job is to go
 * through the board and annotate it, and "who have I not looked at yet" is
 * that job's to-do list — which no combination of the tags themselves can
 * express.
 */

/** Sentinel for "no tags at all". Not a tag key, so it cannot collide. */
export const UNTAGGED = "__untagged__";

export function matchesTagFilter(
  tags: readonly string[] | null | undefined,
  selected: readonly string[],
): boolean {
  if (selected.length === 0) return true;
  const owned = tags ?? [];
  if (owned.length === 0) return selected.includes(UNTAGGED);
  return selected.some((key) => key !== UNTAGGED && owned.includes(key));
}

/** How many players carry each tag, plus how many carry none. Shown on the
 *  chips so the size of what is left to review is visible without filtering. */
export function tagCounts(
  players: readonly { tags?: readonly string[] | null }[],
): Record<string, number> {
  const counts: Record<string, number> = { [UNTAGGED]: 0 };
  for (const player of players) {
    const owned = player.tags ?? [];
    if (owned.length === 0) {
      counts[UNTAGGED] += 1;
      continue;
    }
    // A player tagged twice with the same key counts once.
    for (const key of new Set(owned)) counts[key] = (counts[key] ?? 0) + 1;
  }
  return counts;
}

/** Adds or removes one key from the selection. */
export function toggleTag(selected: readonly string[], key: string): string[] {
  return selected.includes(key)
    ? selected.filter((k) => k !== key)
    : [...selected, key];
}
