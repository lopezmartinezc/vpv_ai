import type { PlayerDraftStats } from "@/types";

export const SUGGESTION_POSITIONS = ["POR", "DEF", "MED", "DEL"] as const;
export const SUGGESTIONS_PER_POSITION = 5;

export type SuggestOrder = "priority" | "vorp" | "gain";

/**
 * Top-N available players per position, by the chosen metric.
 *
 * `pickedIds` is the live set of players already taken, tracked from the pick
 * stream — NOT a flag on the stats payload, which is fetched once when the page
 * opens and would keep proposing someone drafted five picks ago. Excluding them
 * here also means the list refills from below as players go, instead of
 * shrinking.
 *
 * `scoreOf` overrides the field lookup when the ordering is not a column of
 * the payload — "gain" is computed against YOUR roster, which the server has
 * no view of. Players it scores as null drop out, the same as a missing field.
 */
export function buildSuggestions(
  players: Record<string, PlayerDraftStats>,
  order: SuggestOrder,
  pickedIds: ReadonlySet<number>,
  scoreOf?: (p: PlayerDraftStats) => number | null,
): Record<string, number[]> {
  const score = scoreOf ?? ((p: PlayerDraftStats) => (order === "gain" ? null : p[order]));
  const out: Record<string, number[]> = {};
  const pool = Object.values(players);
  for (const pos of SUGGESTION_POSITIONS) {
    out[pos] = pool
      .filter(
        (s) =>
          s.position === pos &&
          score(s) != null &&
          !pickedIds.has(s.player_id),
      )
      .sort((a, b) => (score(b) ?? -1e9) - (score(a) ?? -1e9))
      .slice(0, SUGGESTIONS_PER_POSITION)
      .map((s) => s.player_id);
  }
  return out;
}
