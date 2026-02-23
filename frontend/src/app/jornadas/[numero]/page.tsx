"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { MatchdayDetailResponse } from "@/types";

export default function JornadaDetailPage() {
  const params = useParams<{ numero: string }>();
  const numero = Number(params.numero);
  const { selectedSeason, loading: seasonLoading } = useSeason();

  const { data, loading } = useFetch<MatchdayDetailResponse>(
    selectedSeason ? `/matchdays/${selectedSeason.id}/${numero}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-vpv-text-muted">Cargando jornada...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar la jornada.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/jornadas"
          className="text-sm text-vpv-text-muted transition-colors hover:text-vpv-text"
        >
          &larr; Jornadas
        </Link>
        <h1 className="text-2xl font-bold text-vpv-text">
          Jornada {data.number}
        </h1>
        {!data.counts && (
          <span className="rounded bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-500">
            No computa
          </span>
        )}
      </div>

      {/* Matches */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Partidos
        </h2>
        <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
          <table className="w-full text-sm">
            <tbody>
              {data.matches.map((m) => (
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Participant scores */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Puntuaciones
        </h2>
        <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
                <th className="w-12 px-4 py-3 text-center">#</th>
                <th className="px-4 py-3">Participante</th>
                <th className="px-4 py-3 text-right">Pts</th>
                <th className="hidden px-4 py-3 text-right sm:table-cell">
                  Formacion
                </th>
              </tr>
            </thead>
            <tbody>
              {data.scores.map((s) => (
                <tr
                  key={s.participant_id}
                  className="border-b border-vpv-border transition-colors last:border-0 hover:bg-vpv-accent/5"
                >
                  <td className="px-4 py-3 text-center font-medium text-vpv-text-muted">
                    {s.rank ?? "–"}
                  </td>
                  <td className="px-4 py-3 font-medium text-vpv-text">
                    <Link
                      href={`/jornadas/${numero}/${s.participant_id}`}
                      className="transition-colors hover:text-vpv-accent"
                    >
                      {s.display_name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right font-bold tabular-nums text-vpv-text">
                    {s.total_points}
                  </td>
                  <td className="hidden px-4 py-3 text-right tabular-nums text-vpv-text-muted sm:table-cell">
                    {s.formation ?? "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
