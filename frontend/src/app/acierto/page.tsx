"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SkeletonTable } from "@/components/ui/skeleton";
import type { AccuracyRankingResponse } from "@/types";

const RANK_BADGES: Record<number, string> = {
  1: "bg-amber-400 text-black",
  2: "bg-gray-300 text-black",
  3: "bg-amber-700 text-white",
};

function AccuracyBar({ pct }: { pct: number }) {
  const color =
    pct >= 90 ? "bg-emerald-500" : pct >= 70 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="h-2.5 w-full rounded-full bg-vpv-border overflow-hidden">
      <div
        className={`h-full rounded-full ${color}`}
        style={{ width: `${Math.min(100, pct)}%` }}
      />
    </div>
  );
}

export default function AciertoPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<AccuracyRankingResponse>(
    selectedSeason
      ? `/lineups/${selectedSeason.id}/accuracy/ranking`
      : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-vpv-text">Acierto de Mister</h1>
        <SkeletonTable rows={8} />
      </div>
    );
  }

  if (!data || data.entries.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-vpv-text">Acierto de Mister</h1>
        <p className="text-vpv-text-muted">No hay datos disponibles.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-vpv-text">Acierto de Mister</h1>
        <p className="text-sm text-vpv-text-muted">
          Quien elige mejor su XI cada semana — {data.season_name}
        </p>
      </div>

      {/* Desktop table */}
      <div className="hidden md:block rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
              <th className="px-4 py-2.5 w-12">#</th>
              <th className="px-4 py-2.5">Mister</th>
              <th className="px-4 py-2.5 w-48">Acierto</th>
              <th className="px-4 py-2.5 text-right w-20">%</th>
              <th className="px-4 py-2.5 text-right w-20">Perfectas</th>
              <th className="px-4 py-2.5 text-right w-24">Pts perdidos</th>
              <th className="px-4 py-2.5 text-right w-16">Jorn.</th>
            </tr>
          </thead>
          <tbody>
            {data.entries.map((e) => {
              const badge = RANK_BADGES[e.rank];
              return (
                <tr
                  key={e.participant_id}
                  className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                >
                  <td className="px-4 py-2.5">
                    {badge ? (
                      <span
                        className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${badge}`}
                      >
                        {e.rank}
                      </span>
                    ) : (
                      <span className="text-vpv-text-muted">{e.rank}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-medium text-vpv-text">
                    {e.display_name}
                  </td>
                  <td className="px-4 py-2.5">
                    <AccuracyBar pct={e.avg_accuracy} />
                  </td>
                  <td
                    className={`px-4 py-2.5 text-right font-bold tabular-nums ${
                      e.avg_accuracy >= 90
                        ? "text-emerald-400"
                        : e.avg_accuracy >= 70
                          ? "text-amber-400"
                          : "text-red-400"
                    }`}
                  >
                    {e.avg_accuracy}%
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-vpv-text">
                    {e.perfect_weeks}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-red-400">
                    -{e.total_missed_points}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-vpv-text-muted">
                    {e.matchdays_played}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="space-y-2 md:hidden">
        {data.entries.map((e) => {
          const badge = RANK_BADGES[e.rank];
          return (
            <div
              key={e.participant_id}
              className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3"
            >
              <div className="flex items-center gap-3 mb-2">
                {badge ? (
                  <span
                    className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${badge}`}
                  >
                    {e.rank}
                  </span>
                ) : (
                  <span className="inline-flex h-7 w-7 items-center justify-center text-sm text-vpv-text-muted">
                    {e.rank}
                  </span>
                )}
                <span className="flex-1 font-medium text-vpv-text">
                  {e.display_name}
                </span>
                <span
                  className={`text-lg font-bold tabular-nums ${
                    e.avg_accuracy >= 90
                      ? "text-emerald-400"
                      : e.avg_accuracy >= 70
                        ? "text-amber-400"
                        : "text-red-400"
                  }`}
                >
                  {e.avg_accuracy}%
                </span>
              </div>
              <AccuracyBar pct={e.avg_accuracy} />
              <div className="mt-2 flex items-center gap-4 text-[11px] text-vpv-text-muted">
                <span>Perfectas: {e.perfect_weeks}</span>
                <span className="text-red-400">
                  Perdidos: -{e.total_missed_points}
                </span>
                <span>{e.matchdays_played} jornadas</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
