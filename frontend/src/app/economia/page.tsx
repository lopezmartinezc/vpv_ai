"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { BalanceList } from "@/components/economy/balance-list";
import { SkeletonTable } from "@/components/ui/skeleton";
import { SeasonSelector } from "@/components/layout/season-selector";
import { TournamentHero } from "@/components/tournament/tournament-hero";
import type { EconomyResponse } from "@/types";

export default function EconomiaPage() {
  const { selectedSeason, loading: seasonLoading, isTournamentContext } = useSeason();
  const { data, loading } = useFetch<EconomyResponse>(
    selectedSeason ? `/economy/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={8} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar la economia.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <TournamentHero
        title="Economia"
        subtitle={selectedSeason?.name}
        onlyInTournamentContext
      />
      <div className="flex items-center justify-between gap-4">
        {!isTournamentContext && (
          <h1 className="text-2xl font-bold text-vpv-text">
            Economia {selectedSeason?.name}
          </h1>
        )}
        <SeasonSelector />
      </div>
      <BalanceList balances={data.balances} />
    </div>
  );
}
