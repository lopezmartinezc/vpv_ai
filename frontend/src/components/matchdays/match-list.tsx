import type { MatchEntry } from "@/types";

function formatMatchDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("es-ES", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MatchList({ matches }: { matches: MatchEntry[] }) {
  return (
    <>
      {/* Mobile: Cards */}
      <div className="space-y-2 md:hidden">
        {matches.map((m) => (
          <div
            key={m.id}
            className={`rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3 ${
              !m.counts ? "opacity-50" : ""
            }`}
          >
            <div className="flex items-center">
              <span className="flex-1 truncate text-right text-sm font-medium text-vpv-text">
                {m.home_team}
              </span>
              <span className="mx-3 min-w-[3.5rem] text-center text-base font-bold tabular-nums text-vpv-text">
                {m.home_score ?? "–"} - {m.away_score ?? "–"}
              </span>
              <span className="flex-1 truncate text-sm font-medium text-vpv-text">
                {m.away_team}
              </span>
            </div>
            {m.played_at && (
              <p className="mt-1 text-center text-[11px] text-vpv-text-muted">
                {formatMatchDate(m.played_at)}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden overflow-x-auto rounded-lg border border-vpv-card-border md:block">
        <table className="w-full text-sm">
          <tbody>
            {matches.map((m) => (
              <tr
                key={m.id}
                className={`border-b border-vpv-border last:border-0 ${
                  !m.counts ? "opacity-50" : ""
                }`}
              >
                <td className="px-4 py-2.5 text-right font-medium text-vpv-text">
                  {m.home_team}
                </td>
                <td className="w-20 px-2 py-2.5 text-center font-bold tabular-nums text-vpv-text">
                  {m.home_score ?? "–"} - {m.away_score ?? "–"}
                </td>
                <td className="px-4 py-2.5 font-medium text-vpv-text">
                  {m.away_team}
                </td>
                <td className="px-4 py-2.5 text-right text-xs text-vpv-text-muted">
                  {formatMatchDate(m.played_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
