/**
 * RosterCounter — live composition of a participant's drafted squad vs the
 * recommended target (from the strategy analysis). Forwards are the position
 * most people under-draft, so it flags when you're falling behind on them.
 */

const TARGET: { pos: string; min: number; ideal: number }[] = [
  { pos: "POR", min: 2, ideal: 2 },
  { pos: "DEF", min: 8, ideal: 8 },
  { pos: "MED", min: 7, ideal: 8 },
  { pos: "DEL", min: 6, ideal: 7 },
];

const POS_COLOR: Record<string, string> = {
  POR: "bg-amber-500/20 text-amber-400",
  DEF: "bg-blue-500/20 text-blue-400",
  MED: "bg-emerald-500/20 text-emerald-400",
  DEL: "bg-rose-500/20 text-rose-400",
};

const ROSTER_SIZE = 26;
const DEL_SHARE = 6 / ROSTER_SIZE; // expected pace for forwards

export function RosterCounter({ positions }: { positions: string[] }) {
  const counts: Record<string, number> = {};
  for (const p of positions) counts[p] = (counts[p] ?? 0) + 1;
  const total = positions.length;

  // Behind on forwards if, given how many picks you've made, you have fewer
  // than the pace implies (and you still have room for more).
  const delCount = counts["DEL"] ?? 0;
  const behindOnForwards =
    total >= 6 && delCount < Math.floor(total * DEL_SHARE) && delCount < 7;

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
      <div className="mb-1.5 flex items-baseline justify-between">
        <h4 className="text-xs font-semibold text-vpv-text">Tu plantilla</h4>
        <span className="text-[11px] tabular-nums text-vpv-text-muted">
          {total}/{ROSTER_SIZE}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {TARGET.map((t) => {
          const c = counts[t.pos] ?? 0;
          const met = c >= t.min;
          return (
            <div
              key={t.pos}
              className="flex items-center gap-1.5 rounded border border-vpv-border bg-vpv-bg px-2 py-1"
              title={`objetivo ${t.min}${t.ideal !== t.min ? `-${t.ideal}` : ""}`}
            >
              <span className={`rounded px-1 py-0.5 text-[9px] font-medium ${POS_COLOR[t.pos] ?? ""}`}>
                {t.pos}
              </span>
              <span
                className={`text-sm font-bold tabular-nums ${met ? "text-emerald-400" : "text-vpv-text"}`}
              >
                {c}
              </span>
              <span className="text-[10px] text-vpv-text-muted">/{t.min}</span>
            </div>
          );
        })}
      </div>
      {behindOnForwards && (
        <p className="mt-1.5 text-[11px] text-amber-400">
          ⚠ Vas corto de delanteros — la mejor formación (1-4-3-3) pide 3 y hace falta fondo.
        </p>
      )}
    </div>
  );
}
