"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { CopaFullResponse } from "@/types";
import { CopaStandings } from "@/components/copa/copa-standings";
import { CopaMatchdays } from "@/components/copa/copa-matchday-detail";
import { SkeletonCards } from "@/components/ui/skeleton";

export default function CopaPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading, error } = useFetch<CopaFullResponse>(
    selectedSeason ? `/copa/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 animate-pulse rounded bg-vpv-border" />
        <SkeletonCards count={3} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">No se pudo cargar la Copa</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-vpv-text">Copa VPV</h1>
        <p className="mt-1 text-vpv-text-muted">
          Temporada {data.season_name}
        </p>
      </div>

      <CopaStandings entries={data.standings} />

      {data.matchdays.length > 0 && (
        <CopaMatchdays matchdays={data.matchdays} />
      )}
    </div>
  );
}
