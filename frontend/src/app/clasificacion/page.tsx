"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { StandingsList } from "@/components/standings/standings-list";
import { LigaMatchdayDetail } from "@/components/standings/liga-matchday-detail";
import { EvolutionChart } from "@/components/standings/evolution-chart";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Logo } from "@/components/ui/logo";
import type { StandingsResponse, MatchdayListResponse } from "@/types";

interface EvolutionEntry {
  matchday_number: number;
  participant_id: number;
  display_name: string;
  points: number;
  cumulative: number;
}

interface EvolutionResponse {
  season_id: number;
  entries: EvolutionEntry[];
}

export default function ClasificacionPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data: standings, loading: standingsLoading } =
    useFetch<StandingsResponse>(
      selectedSeason ? `/standings/${selectedSeason.id}` : null,
    );
  const { data: matchdayList, loading: matchdaysLoading } =
    useFetch<MatchdayListResponse>(
      selectedSeason ? `/matchdays/${selectedSeason.id}` : null,
    );
  const { data: evolution } = useFetch<EvolutionResponse>(
    selectedSeason ? `/standings/${selectedSeason.id}/evolution` : null,
  );

  if (seasonLoading || standingsLoading || matchdaysLoading) {
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
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Logo className="h-16 w-auto text-vpv-accent" />
        <p className="text-sm text-vpv-text-muted">
          Temporada {standings.season_name}
        </p>
      </div>

      <StandingsList entries={standings.entries} />

      {evolution && evolution.entries.length > 0 && (
        <EvolutionChart entries={evolution.entries} />
      )}

      {selectedSeason && matchdayList && matchdayList.matchdays.length > 0 && (
        <LigaMatchdayDetail
          seasonId={selectedSeason.id}
          matchdays={matchdayList.matchdays}
          matchdayCurrent={selectedSeason.matchday_current}
        />
      )}
    </div>
  );
}
