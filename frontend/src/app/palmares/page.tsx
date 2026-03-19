"use client";

import { useFetch } from "@/hooks/use-fetch";
import { SkeletonTable } from "@/components/ui/skeleton";
import type { PalmaresResponse } from "@/types";

const RANK_STYLE: Record<number, { bg: string; emoji: string }> = {
  1: { bg: "bg-amber-400 text-black", emoji: "\uD83E\uDD47" },
  2: { bg: "bg-gray-300 text-black", emoji: "\uD83E\uDD48" },
  3: { bg: "bg-amber-700 text-white", emoji: "\uD83E\uDD49" },
};

export default function PalmaresPage() {
  const { data, loading } = useFetch<PalmaresResponse>("/palmares");

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-vpv-text">Palmares</h1>
        <SkeletonTable rows={6} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-vpv-text">Palmares</h1>
        <p className="text-vpv-text-muted">No hay datos disponibles.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-vpv-text">Palmares</h1>
        <p className="text-sm text-vpv-text-muted">
          Historial de la Liga VPV Fantasy
        </p>
      </div>

      {/* Records */}
      {data.records.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-vpv-text">
            Records historicos
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {data.records.map((r, i) => (
              <div
                key={i}
                className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3"
              >
                <p className="text-[11px] font-semibold uppercase text-vpv-text-muted">
                  {r.label}
                </p>
                <p className="mt-1 text-xl font-bold text-vpv-accent">
                  {r.value}
                </p>
                <p className="mt-0.5 text-xs text-vpv-text-muted">{r.detail}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Champions by season */}
      {data.champions.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-vpv-text">
            Campeonatos
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data.champions.map((season) => (
              <div
                key={season.season_id}
                className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden"
              >
                <div className="border-b border-vpv-border bg-vpv-bg px-4 py-2">
                  <span className="text-sm font-semibold text-vpv-text">
                    {season.season_name}
                  </span>
                </div>
                <div className="px-4 py-3 space-y-2">
                  {season.entries.map((e) => {
                    const style = RANK_STYLE[e.rank];
                    return (
                      <div key={e.user_id} className="flex items-center gap-2.5">
                        {style ? (
                          <span className="text-lg">{style.emoji}</span>
                        ) : (
                          <span className="w-5 text-center text-sm text-vpv-text-muted">
                            {e.rank}
                          </span>
                        )}
                        <span className="flex-1 text-sm font-medium text-vpv-text">
                          {e.display_name}
                        </span>
                        <span className="text-xs tabular-nums text-vpv-text-muted">
                          {e.total_points.toLocaleString()} pts
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Career stats */}
      {data.career.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-vpv-text">
            Ranking historico
          </h2>

          {/* Desktop table */}
          <div className="hidden md:block rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
                  <th className="px-4 py-2.5">Participante</th>
                  <th className="px-4 py-2.5 text-center w-16">Temp.</th>
                  <th className="px-4 py-2.5 text-center w-20">Titulos</th>
                  <th className="px-4 py-2.5 text-center w-20">Podios</th>
                  <th className="px-4 py-2.5 text-right w-24">Pts totales</th>
                  <th className="px-4 py-2.5 text-right w-20">Media</th>
                  <th className="px-4 py-2.5 text-center w-16">Mejor</th>
                </tr>
              </thead>
              <tbody>
                {data.career.map((c) => (
                  <tr
                    key={c.user_id}
                    className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                  >
                    <td className="px-4 py-2.5 font-medium text-vpv-text">
                      {c.display_name}
                    </td>
                    <td className="px-4 py-2.5 text-center tabular-nums text-vpv-text-muted">
                      {c.seasons_played}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {c.championships > 0 ? (
                        <span className="font-bold text-amber-400">
                          {"\uD83C\uDFC6".repeat(c.championships)}
                        </span>
                      ) : (
                        <span className="text-vpv-text-muted">-</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center tabular-nums text-vpv-text">
                      {c.podiums}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-medium text-vpv-text">
                      {c.total_points.toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-vpv-text-muted">
                      {c.avg_points}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {c.best_finish > 0 ? (
                        <span className={c.best_finish <= 3 ? "font-bold text-amber-400" : "text-vpv-text-muted"}>
                          {c.best_finish}o
                        </span>
                      ) : (
                        <span className="text-vpv-text-muted">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="space-y-2 md:hidden">
            {data.career.map((c) => (
              <div
                key={c.user_id}
                className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-vpv-text">
                    {c.display_name}
                  </span>
                  {c.championships > 0 && (
                    <span className="text-amber-400">
                      {"\uD83C\uDFC6".repeat(c.championships)}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-3 text-[11px] text-vpv-text-muted">
                  <span>{c.seasons_played} temp.</span>
                  <span>{c.podiums} podios</span>
                  <span>{c.total_points.toLocaleString()} pts</span>
                  <span>Media: {c.avg_points}</span>
                  {c.best_finish > 0 && <span>Mejor: {c.best_finish}o</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
