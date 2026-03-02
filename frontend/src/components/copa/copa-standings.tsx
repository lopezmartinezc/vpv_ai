"use client";

import type { CopaStandingEntry } from "@/types";

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1)
    return (
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-vpv-gold text-xs font-bold text-black">
        1
      </span>
    );
  if (rank === 2)
    return (
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-gray-300 text-xs font-bold text-black">
        2
      </span>
    );
  if (rank === 3)
    return (
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-amber-700 text-xs font-bold text-white">
        3
      </span>
    );
  return (
    <span className="inline-flex h-7 w-7 items-center justify-center text-sm text-vpv-text-muted">
      {rank}
    </span>
  );
}

function ResultBadge({ value, label }: { value: number; label: string }) {
  const colors: Record<string, string> = {
    G: "text-vpv-success",
    E: "text-vpv-text-muted",
    P: "text-vpv-danger",
  };
  return (
    <span className={`tabular-nums ${colors[label] ?? "text-vpv-text"}`}>
      {value}
    </span>
  );
}

export function CopaStandings({
  entries,
}: {
  entries: CopaStandingEntry[];
}) {
  return (
    <>
      {/* Mobile: Cards */}
      <div className="space-y-2 md:hidden">
        {entries.map((e) => (
          <div
            key={e.participant_id}
            className="flex items-center gap-3 rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3"
          >
            <RankBadge rank={e.rank} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-vpv-text">
                {e.display_name}
              </p>
              <p className="text-xs text-vpv-text-muted">
                {e.matches_played}PJ &middot;{" "}
                <ResultBadge value={e.wins} label="G" />-
                <ResultBadge value={e.draws} label="E" />-
                <ResultBadge value={e.losses} label="P" /> &middot; DG{" "}
                <span
                  className={`font-bold ${e.goal_difference > 0 ? "text-vpv-success" : e.goal_difference < 0 ? "text-vpv-danger" : "text-vpv-text-muted"}`}
                >
                  {e.goal_difference > 0
                    ? `+${e.goal_difference}`
                    : e.goal_difference}
                </span>
              </p>
            </div>
            <span className="text-lg font-bold tabular-nums text-vpv-text">
              {e.total_points}
            </span>
          </div>
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
              <th className="px-4 py-3 text-right">PJ</th>
              <th className="px-4 py-3 text-right">G</th>
              <th className="px-4 py-3 text-right">E</th>
              <th className="px-4 py-3 text-right">P</th>
              <th className="px-4 py-3 text-right">GF</th>
              <th className="px-4 py-3 text-right">GC</th>
              <th className="px-4 py-3 text-right">DG</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr
                key={e.participant_id}
                className="border-b border-vpv-border transition-colors last:border-0 hover:bg-vpv-accent/5"
              >
                <td className="px-4 py-3 text-center">
                  <RankBadge rank={e.rank} />
                </td>
                <td className="px-4 py-3 font-medium text-vpv-text">
                  {e.display_name}
                </td>
                <td className="px-4 py-3 text-right font-bold tabular-nums text-vpv-text">
                  {e.total_points}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {e.matches_played}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-success">
                  {e.wins}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {e.draws}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-danger">
                  {e.losses}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {e.total_goals_for}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {e.total_goals_against}
                </td>
                <td
                  className={`px-4 py-3 text-right font-bold tabular-nums ${e.goal_difference > 0 ? "text-vpv-success" : e.goal_difference < 0 ? "text-vpv-danger" : "text-vpv-text-muted"}`}
                >
                  {e.goal_difference > 0
                    ? `+${e.goal_difference}`
                    : e.goal_difference}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
