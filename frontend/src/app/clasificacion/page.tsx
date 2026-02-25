"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { StandingsList } from "@/components/standings/standings-list";
import { SkeletonTable } from "@/components/ui/skeleton";
import { SeasonSelector } from "@/components/layout/season-selector";
import type { StandingsResponse } from "@/types";

export default function ClasificacionPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data: standings, loading } = useFetch<StandingsResponse>(
    selectedSeason ? `/standings/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={8} />
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
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">
          Clasificacion {standings.season_name}
        </h1>
        <SeasonSelector />
      </div>
      <StandingsList entries={standings.entries} />
    </div>
  );
}
