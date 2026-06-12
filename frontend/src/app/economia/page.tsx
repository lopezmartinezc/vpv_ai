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
  const economyEnabled = selectedSeason?.weekly_payments_enabled !== false;
  const { data, loading } = useFetch<EconomyResponse>(
    selectedSeason && economyEnabled ? `/economy/${selectedSeason.id}` : null,
  );

  if (seasonLoading || (economyEnabled && loading)) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={8} />
      </div>
    );
  }

  // The season opted out of the weekly-payments mechanic — make this
  // explicit instead of showing an empty table when a user lands here
  // via a stale bookmark.
  if (!economyEnabled) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-vpv-text">Economía</h1>
          <SeasonSelector />
        </div>
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-6 text-center text-sm text-vpv-text-muted">
          Esta temporada no usa el sistema de pagos semanales.
          {selectedSeason?.kind === "tournament" && (
            <>
              {" "}
              Los torneos cortos (Mundial, Eurocopa, …) suelen liquidarse fuera de la app.
            </>
          )}
        </div>
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
