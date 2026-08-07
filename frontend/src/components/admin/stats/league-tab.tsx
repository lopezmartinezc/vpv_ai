import type {
  FormationUsage,
  MatchdayAverageEntry,
  RecordEntry,
} from "@/types";

export function LeagueTab({
  formations,
  matchdayAverages,
  records,
}: {
  formations: FormationUsage[];
  matchdayAverages: MatchdayAverageEntry[];
  records: RecordEntry[];
}) {
  return (
    <div className="space-y-4">
      {/* Records */}
      {records.length > 0 && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
          <div className="border-b border-vpv-border px-4 py-3">
            <h3 className="font-semibold text-vpv-text">Records</h3>
          </div>
          <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
            {records.map((r, i) => (
              <div
                key={i}
                className="rounded-lg border border-vpv-border bg-vpv-bg p-3"
              >
                <p className="text-xs text-vpv-text-muted">{r.label}</p>
                <p className="text-lg font-bold text-vpv-accent">{r.value}</p>
                <p className="text-xs text-vpv-text-muted">{r.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Formation usage */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h3 className="font-semibold text-vpv-text">Uso de formaciones</h3>
        </div>
        <div className="p-4">
          {formations.length === 0 ? (
            <p className="text-sm text-vpv-text-muted">Sin datos</p>
          ) : (
            <div className="space-y-2">
              {formations.map((f) => {
                const maxCount = formations[0].usage_count;
                const pct = maxCount > 0 ? (f.usage_count / maxCount) * 100 : 0;
                return (
                  <div key={f.formation} className="flex items-center gap-3">
                    <span className="w-20 text-sm font-medium text-vpv-text">
                      {f.formation}
                    </span>
                    <div className="flex-1">
                      <div className="h-5 rounded-full bg-vpv-border">
                        <div
                          className="flex h-5 items-center rounded-full bg-vpv-accent px-2 text-xs font-medium text-white"
                          style={{ width: `${Math.max(pct, 8)}%` }}
                        >
                          {f.usage_count}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Matchday averages */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h3 className="font-semibold text-vpv-text">Medias por jornada</h3>
        </div>
        {matchdayAverages.length === 0 ? (
          <p className="px-4 py-6 text-sm text-vpv-text-muted">
            Sin jornadas puntuadas todavia.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vpv-border bg-vpv-bg text-left text-xs text-vpv-text-muted">
                  <th className="px-3 py-2">Jornada</th>
                  <th className="px-3 py-2 text-right">Media</th>
                  <th className="px-3 py-2 text-right">Max</th>
                  <th className="px-3 py-2 text-right">Min</th>
                </tr>
              </thead>
              <tbody>
                {matchdayAverages.map((md) => (
                  <tr
                    key={md.matchday_number}
                    className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                  >
                    <td className="px-3 py-1.5 font-medium text-vpv-text">
                      J{md.matchday_number}
                    </td>
                    <td className="px-3 py-1.5 text-right font-medium text-vpv-accent">
                      {md.avg_points.toFixed(1)}
                    </td>
                    <td className="px-3 py-1.5 text-right text-green-400">
                      {md.max_points}
                    </td>
                    <td className="px-3 py-1.5 text-right text-red-400">
                      {md.min_points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Advanced Tab
// ---------------------------------------------------------------------------
