/**
 * What a pick is worth TO YOUR TEAM, as opposed to in the abstract.
 *
 * Prioridad ranks players against the whole league. VORP corrects for
 * positional scarcity, but against a generic 1-4-3-3, not against the squad you
 * actually have. Neither can see that your midfield is already the best on the
 * board, so the 448-point midfielder would displace a 436-point one and earn
 * you twelve points, while the 390-point defender walks into an empty slot and
 * earns you all 390.
 *
 * "Alignable points" is the honest unit: the best XI you can field under the
 * league's valid formations, before and after the pick. It is a snapshot of
 * today's squad — it does not try to guess which players are still coming.
 */

export interface Formation {
  formation: string;
  defenders: number;
  midfielders: number;
  forwards: number;
}

export interface RosterPlayer {
  position: string;
  priority: number | null;
}

const LINE_KEY: Record<string, keyof Pick<Formation, "defenders" | "midfielders" | "forwards">> = {
  DEF: "defenders",
  MED: "midfielders",
  DEL: "forwards",
};

function bestOf(players: RosterPlayer[], position: string, take: number): number {
  return players
    .filter((p) => p.position === position && p.priority !== null)
    .map((p) => p.priority as number)
    .sort((a, b) => b - a)
    .slice(0, take)
    .reduce((a, b) => a + b, 0);
}

/**
 * Points of the strongest XI this squad can field, across every valid
 * formation. An incomplete squad simply fields fewer than eleven rather than
 * scoring zero — mid-draft nobody has a full team yet, and the comparison still
 * has to work.
 */
export function bestXiPoints(players: RosterPlayer[], formations: Formation[]): number {
  const keeper = bestOf(players, "POR", 1);
  if (formations.length === 0) return keeper;
  return Math.max(
    ...formations.map(
      (f) =>
        keeper +
        bestOf(players, "DEF", f.defenders) +
        bestOf(players, "MED", f.midfielders) +
        bestOf(players, "DEL", f.forwards),
    ),
  );
}

/**
 * Alignable points gained by adding this player to the squad.
 *
 * Zero means he would not make today's XI — which is not the same as worthless:
 * squads need cover, and a late-round bench player who never starts still
 * covers an injury. Read it as "how much he improves you right now", and let
 * Prioridad speak for what he is worth in himself.
 */
export function rosterGain(
  candidate: RosterPlayer,
  myPlayers: RosterPlayer[],
  formations: Formation[],
): number {
  if (candidate.priority === null) return 0;
  if (LINE_KEY[candidate.position] === undefined && candidate.position !== "POR") return 0;
  const before = bestXiPoints(myPlayers, formations);
  const after = bestXiPoints([...myPlayers, candidate], formations);
  // A pick can never make the XI worse; guard against float drift only.
  return Math.max(0, Math.round((after - before) * 10) / 10);
}
