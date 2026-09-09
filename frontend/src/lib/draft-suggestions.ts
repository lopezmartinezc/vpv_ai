import type { PlayerDraftStats } from "@/types";

export const SUGGESTION_POSITIONS = ["POR", "DEF", "MED", "DEL"] as const;
export const SUGGESTIONS_PER_POSITION = 5;

export type SuggestOrder = "priority" | "vorp";

/**
 * Top-N available players per position, by the chosen metric.
 *
 * `pickedIds` is the live set of players already taken, tracked from the pick
 * stream — NOT a flag on the stats payload, which is fetched once when the page
 * opens and would keep proposing someone drafted five picks ago. Excluding them
 * here also means the list refills from below as players go, instead of
 * shrinking.
 */
export function buildSuggestions(
  players: Record<string, PlayerDraftStats>,
  order: SuggestOrder,
  pickedIds: ReadonlySet<number>,
): Record<string, number[]> {
  const out: Record<string, number[]> = {};
  const pool = Object.values(players);
  for (const pos of SUGGESTION_POSITIONS) {
    out[pos] = pool
      .filter(
        (s) =>
          s.position === pos &&
          s[order] != null &&
          !pickedIds.has(s.player_id),
      )
      .sort((a, b) => (b[order] ?? -1e9) - (a[order] ?? -1e9))
      .slice(0, SUGGESTIONS_PER_POSITION)
      .map((s) => s.player_id);
  }
  return out;
}
