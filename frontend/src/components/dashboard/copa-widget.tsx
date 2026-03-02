import Link from "next/link";
import type { CopaStandingEntry } from "@/types";

const RANK_STYLES: Record<number, { badge: string }> = {
  1: { badge: "bg-vpv-gold text-black" },
  2: { badge: "bg-gray-300 text-black" },
  3: { badge: "bg-amber-700 text-white" },
};

export function CopaWidget({ entries }: { entries: CopaStandingEntry[] }) {
  if (entries.length === 0) return null;

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Copa VPV
        </h2>
        <Link
          href="/copa"
          className="text-xs text-vpv-accent transition-colors hover:text-vpv-accent-hover"
        >
          Ver copa &rarr;
        </Link>
      </div>

      <div className="mt-3 space-y-2">
        {entries.map((entry) => {
          const style = RANK_STYLES[entry.rank] ?? {
            badge: "bg-vpv-border text-vpv-text-muted",
          };

          return (
            <div key={entry.participant_id} className="flex items-center gap-3">
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${style.badge}`}
              >
                {entry.rank}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className={`truncate font-medium ${entry.rank === 1 ? "text-vpv-accent" : "text-vpv-text"}`}
                >
                  {entry.display_name}
                </p>
              </div>
              <span className="text-xs tabular-nums text-vpv-text-muted">
                DG{" "}
                {entry.goal_difference > 0
                  ? `+${entry.goal_difference}`
                  : entry.goal_difference}
              </span>
              <span
                className={`text-sm font-bold tabular-nums ${entry.rank === 1 ? "text-vpv-accent" : "text-vpv-text"}`}
              >
                {entry.total_points}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
