import Link from "next/link";
import type { MatchdayDetailResponse } from "@/types";

export function LastMatchday({ data }: { data: MatchdayDetailResponse }) {
  const topScores = data.scores.slice(0, 5);

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Ultima jornada
        </h2>
        <Link
          href={`/jornadas/${data.number}`}
          className="text-xs text-vpv-accent transition-colors hover:text-vpv-accent-hover"
        >
          Ver completa &rarr;
        </Link>
      </div>

      <p className="mt-1 text-lg font-bold text-vpv-text">
        Jornada {data.number}
      </p>

      <div className="mt-3 space-y-1.5">
        {topScores.map((s, i) => (
          <div
            key={s.participant_id}
            className="flex items-center justify-between text-sm"
          >
            <div className="flex items-center gap-2">
              <span className="w-5 text-center text-xs font-medium text-vpv-text-muted">
                {i + 1}
              </span>
              <span
                className={`font-medium ${i === 0 ? "text-vpv-accent" : "text-vpv-text"}`}
              >
                {s.display_name}
              </span>
            </div>
            <span
              className={`font-bold tabular-nums ${i === 0 ? "text-vpv-accent" : "text-vpv-text"}`}
            >
              {s.total_points}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
