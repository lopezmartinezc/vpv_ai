import type { StandingEntry } from "@/types";

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

export function StandingsList({ entries }: { entries: StandingEntry[] }) {
  return (
    <>
      {/* Mobile: Cards */}
      <div className="space-y-2 md:hidden">
        {entries.map((entry) => (
          <div
            key={entry.participant_id}
            className="flex items-center gap-3 rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3"
          >
            <RankBadge rank={entry.rank} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-vpv-text">
                {entry.display_name}
              </p>
              <p className="text-xs text-vpv-text-muted">
                {entry.matchdays_played} jornadas &middot; Media{" "}
                {entry.avg_points.toFixed(1)}
              </p>
            </div>
            <span className="text-lg font-bold tabular-nums text-vpv-text">
              {entry.total_points}
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
              <th className="px-4 py-3 text-right">Jornadas</th>
              <th className="px-4 py-3 text-right">Media</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr
                key={entry.participant_id}
                className="border-b border-vpv-border transition-colors last:border-0 hover:bg-vpv-accent/5"
              >
                <td className="px-4 py-3 text-center font-medium">
                  <RankBadge rank={entry.rank} />
                </td>
                <td className="px-4 py-3 font-medium text-vpv-text">
                  {entry.display_name}
                </td>
                <td className="px-4 py-3 text-right font-bold tabular-nums text-vpv-text">
                  {entry.total_points}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {entry.matchdays_played}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {entry.avg_points.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
