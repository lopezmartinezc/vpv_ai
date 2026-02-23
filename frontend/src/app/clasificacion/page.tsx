"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { StandingsResponse } from "@/types";

export default function ClasificacionPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data: standings, loading } = useFetch<StandingsResponse>(
    selectedSeason ? `/standings/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-vpv-text-muted">Cargando clasificacion...</p>
      </div>
    );
  }

  if (!standings) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar la clasificacion.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-vpv-text">
        Clasificacion {standings.season_name}
      </h1>

      <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="w-12 px-4 py-3 text-center">#</th>
              <th className="px-4 py-3">Participante</th>
              <th className="px-4 py-3 text-right">Pts</th>
              <th className="hidden px-4 py-3 text-right sm:table-cell">
                Jornadas
              </th>
              <th className="hidden px-4 py-3 text-right sm:table-cell">
                Media
              </th>
            </tr>
          </thead>
          <tbody>
            {standings.entries.map((entry) => (
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
                <td className="hidden px-4 py-3 text-right tabular-nums text-vpv-text-muted sm:table-cell">
                  {entry.matchdays_played}
                </td>
                <td className="hidden px-4 py-3 text-right tabular-nums text-vpv-text-muted sm:table-cell">
                  {entry.avg_points.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1)
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-vpv-gold text-xs font-bold text-black">
        1
      </span>
    );
  if (rank === 2)
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-gray-300 text-xs font-bold text-black">
        2
      </span>
    );
  if (rank === 3)
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-amber-700 text-xs font-bold text-white">
        3
      </span>
    );
  return <span className="text-vpv-text-muted">{rank}</span>;
}
