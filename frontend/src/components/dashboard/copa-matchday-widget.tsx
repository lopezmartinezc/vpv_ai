import Link from "next/link";
import type { CopaMatchdayDetail } from "@/types";

function ResultLabel({ points }: { points: number }) {
  if (points === 3)
    return (
      <span className="rounded bg-vpv-success/20 px-1.5 py-0.5 text-[10px] font-bold text-vpv-success">
        V
      </span>
    );
  if (points === 1)
    return (
      <span className="rounded bg-vpv-text-muted/20 px-1.5 py-0.5 text-[10px] font-bold text-vpv-text-muted">
        E
      </span>
    );
  return (
    <span className="rounded bg-vpv-danger/20 px-1.5 py-0.5 text-[10px] font-bold text-vpv-danger">
      D
    </span>
  );
}

export function CopaMatchdayWidget({
  matchday,
}: {
  matchday: CopaMatchdayDetail;
}) {
  const sorted = [...matchday.results].sort(
    (a, b) => b.points - a.points || b.goal_difference - a.goal_difference,
  );

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
            Copa — Jornada actual
          </h2>
          <p className="text-lg font-bold text-vpv-text">
            Jornada {matchday.matchday_number}
          </p>
        </div>
        <Link
          href="/copa"
          className="text-xs text-vpv-accent transition-colors hover:text-vpv-accent-hover"
        >
          Ver copa &rarr;
        </Link>
      </div>

      <div className="px-4 pb-3">
        <div className="divide-y divide-vpv-border/50">
          {sorted.map((r) => (
            <div
              key={r.participant_id}
              className="flex items-center gap-2 py-1.5 text-sm"
            >
              <ResultLabel points={r.points} />
              <span className="min-w-0 flex-1 truncate font-medium text-vpv-text">
                {r.display_name}
              </span>
              <span className="tabular-nums text-vpv-text">
                {r.goals_for}-{r.goals_against}
              </span>
              <span
                className={`w-8 text-right text-xs font-bold tabular-nums ${r.goal_difference > 0 ? "text-vpv-success" : r.goal_difference < 0 ? "text-vpv-danger" : "text-vpv-text-muted"}`}
              >
                {r.goal_difference > 0
                  ? `+${r.goal_difference}`
                  : r.goal_difference}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
