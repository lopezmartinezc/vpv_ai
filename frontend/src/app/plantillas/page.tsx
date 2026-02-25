"use client";

import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SeasonSelector } from "@/components/layout/season-selector";
import type { SquadListResponse } from "@/types";

const POSITION_LABELS = ["POR", "DEF", "MED", "DEL"] as const;

export default function PlantillasPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<SquadListResponse>(
    selectedSeason ? `/squads/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-vpv-border" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-lg bg-vpv-border"
            />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudieron cargar las plantillas.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">
          Plantillas {selectedSeason?.name}
        </h1>
        <SeasonSelector />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.squads.map((squad) => (
          <Link
            key={squad.participant_id}
            href={`/plantillas/${squad.participant_id}`}
            className="rounded-lg border border-vpv-card-border bg-vpv-card p-4 transition-colors hover:border-vpv-accent"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-vpv-text">
                {squad.display_name}
              </h2>
              <span className="text-lg font-bold tabular-nums text-vpv-accent">
                {squad.season_points}
              </span>
            </div>

            <p className="mt-1 text-sm text-vpv-text-muted">
              {squad.total_players} jugadores
            </p>

            <div className="mt-3 flex gap-2">
              {POSITION_LABELS.map((pos) => (
                <span
                  key={pos}
                  className="rounded bg-vpv-bg px-2 py-0.5 text-xs tabular-nums text-vpv-text-muted"
                >
                  {pos} {squad.positions[pos]}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
