import type { SquadPlayerEntry, ValidFormation } from "@/types";

export const POSITION_ORDER = ["POR", "DEF", "MED", "DEL"] as const;
export type Position = (typeof POSITION_ORDER)[number];

export const POSITION_LABELS: Record<Position, string> = {
  POR: "Porteros",
  DEF: "Defensas",
  MED: "Centrocampistas",
  DEL: "Delanteros",
};

export const POSITION_COLORS: Record<Position, string> = {
  POR: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  DEF: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  MED: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  DEL: "bg-rose-500/15 text-rose-400 border-rose-500/30",
};

export function countsByPosition(
  selected: SquadPlayerEntry[],
): Record<Position, number> {
  return {
    POR: selected.filter((p) => p.position === "POR").length,
    DEF: selected.filter((p) => p.position === "DEF").length,
    MED: selected.filter((p) => p.position === "MED").length,
    DEL: selected.filter((p) => p.position === "DEL").length,
  };
}

/** Check if a player of the given position can be added without making it
 *  impossible to reach any valid formation. */
export function canAddToPosition(
  pos: Position,
  counts: Record<Position, number>,
  formations: ValidFormation[],
  total: number,
): boolean {
  if (total >= 11) return false;
  if (pos === "POR") return counts.POR < 1;
  const next = { ...counts, [pos]: counts[pos] + 1 };
  return formations.some(
    (f) =>
      next.DEF <= f.defenders &&
      next.MED <= f.midfielders &&
      next.DEL <= f.forwards,
  );
}
