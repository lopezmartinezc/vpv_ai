"use client";

import { useSeason } from "@/contexts/season-context";
import type { ReactNode } from "react";

/**
 * Renders children only if the currently selected season is a league.
 * In tournament context, shows a hint with a one-click switch to the
 * active Liga season (if any).
 *
 * Use for pages/sections that don't apply to tournaments: Copa, Palmares,
 * Achievements, etc.
 */
export function LeagueOnlyGuard({
  children,
  pageName = "Esta seccion",
}: {
  children: ReactNode;
  pageName?: string;
}) {
  const { isTournamentContext, activeLeague, selectSeason, selectedSeason } =
    useSeason();

  if (!isTournamentContext) return <>{children}</>;

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
      <p className="text-lg font-medium text-vpv-text">
        {pageName} solo aplica a la Liga
      </p>
      <p className="mt-2 text-sm text-vpv-text-muted">
        Estas viendo el contexto de{" "}
        <strong>{selectedSeason?.name}</strong> (torneo).
      </p>
      {activeLeague && (
        <button
          type="button"
          onClick={() => selectSeason(activeLeague.id)}
          className="mt-4 rounded bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80"
        >
          Cambiar a {activeLeague.name}
        </button>
      )}
    </div>
  );
}
