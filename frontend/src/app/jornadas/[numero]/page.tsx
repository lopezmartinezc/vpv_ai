"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { MatchList } from "@/components/matchdays/match-list";
import { MatchdayAccordion } from "@/components/dashboard/matchday-accordion";
import { SkeletonTable } from "@/components/ui/skeleton";
import type { MatchdayDetailResponse } from "@/types";

export default function JornadaDetailPage() {
  const params = useParams<{ numero: string }>();
  const numero = Number(params.numero);
  const { user } = useAuth();
  const { selectedSeason, loading: seasonLoading } = useSeason();

  const { data, loading } = useFetch<MatchdayDetailResponse>(
    selectedSeason ? `/matchdays/${selectedSeason.id}/${numero}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={5} />
        <SkeletonTable rows={8} />
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
        {user && (
          <Link
            href={`/jornadas/${numero}/alineacion`}
            className="ml-auto rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80"
          >
            Enviar alineacion
          </Link>
        )}
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Partidos
        </h2>
        <MatchList matches={data.matches} />
      </section>

      {selectedSeason && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
            Puntuaciones
          </h2>
          <MatchdayAccordion data={data} seasonId={selectedSeason.id} showHeader={false} />
        </section>
      )}
    </div>
  );
}
