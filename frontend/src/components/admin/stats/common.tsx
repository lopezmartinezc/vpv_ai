/** Shared helpers for the admin statistics tabs. */

export type SortDir = "asc" | "desc";

/** Generic client-side sort — null/undefined values are pushed to the end. */
export function sorted<T>(items: T[], key: keyof T, dir: SortDir): T[] {
  return [...items].sort((a, b) => {
    const va = a[key];
    const vb = b[key];
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    if (va < vb) return dir === "asc" ? -1 : 1;
    if (va > vb) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

export const POS_COLOR: Record<string, string> = {
  POR: "bg-amber-500/20 text-amber-400",
  DEF: "bg-blue-500/20 text-blue-400",
  MED: "bg-emerald-500/20 text-emerald-400",
  DEL: "bg-rose-500/20 text-rose-400",
};
