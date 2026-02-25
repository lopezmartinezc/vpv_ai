import Link from "next/link";
import type { ParticipantScore } from "@/types";

interface ScoreListProps {
  scores: ParticipantScore[];
  matchdayNumber: number;
}

export function ScoreList({ scores, matchdayNumber }: ScoreListProps) {
  return (
    <>
      {/* Mobile: Cards */}
      <div className="space-y-2 md:hidden">
        {scores.map((s) => (
          <Link
            key={s.participant_id}
            href={`/jornadas/${matchdayNumber}/${s.participant_id}`}
            className="flex items-center gap-3 rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3 transition-colors hover:border-vpv-accent"
          >
            <span className="w-6 text-center text-sm font-medium text-vpv-text-muted">
              {s.rank ?? "–"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-vpv-text">
                {s.display_name}
              </p>
              {s.formation && (
                <p className="text-xs text-vpv-text-muted">{s.formation}</p>
              )}
            </div>
            <span className="text-lg font-bold tabular-nums text-vpv-text">
              {s.total_points}
            </span>
          </Link>
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden overflow-x-auto rounded-lg border border-vpv-card-border md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="w-12 px-4 py-3 text-center">#</th>
              <th className="px-4 py-3">Participante</th>
              <th className="px-4 py-3 text-right">Pts</th>
              <th className="px-4 py-3 text-right">Formacion</th>
            </tr>
          </thead>
          <tbody>
            {scores.map((s) => (
              <tr
                key={s.participant_id}
                className="border-b border-vpv-border transition-colors last:border-0 hover:bg-vpv-accent/5"
              >
                <td className="px-4 py-3 text-center font-medium text-vpv-text-muted">
                  {s.rank ?? "–"}
                </td>
                <td className="px-4 py-3 font-medium text-vpv-text">
                  <Link
                    href={`/jornadas/${matchdayNumber}/${s.participant_id}`}
                    className="transition-colors hover:text-vpv-accent"
                  >
                    {s.display_name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-right font-bold tabular-nums text-vpv-text">
                  {s.total_points}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {s.formation ?? "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
