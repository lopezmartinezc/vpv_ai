"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SeasonSelector } from "@/components/layout/season-selector";
import type { SquadListResponse } from "@/types";

const POSITION_LABELS = ["POR", "DEF", "MED", "DEL"] as const;

export default function PlantillasPage() {
  return (
    <Suspense
      fallback={
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
      }
    >
      <PlantillasContent />
    </Suspense>
  );
}

function PlantillasContent() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const searchParams = useSearchParams();
  const router = useRouter();
  const jornada = searchParams.get("jornada");

  const apiPath = selectedSeason
    ? `/squads/${selectedSeason.id}${jornada ? `?matchday=${jornada}` : ""}`
    : null;

  const { data, loading } = useFetch<SquadListResponse>(apiPath);

  function handleJornadaChange(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("jornada", value);
    } else {
      params.delete("jornada");
    }
    router.replace(`/plantillas?${params.toString()}`);
  }

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
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">
          Plantillas {selectedSeason?.name}
        </h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-vpv-text-muted">
            Jornada
            <input
              type="number"
              min={1}
              max={38}
              value={jornada ?? ""}
              placeholder="Actual"
              onChange={(e) => handleJornadaChange(e.target.value)}
              className="w-20 rounded border border-vpv-border bg-vpv-card px-2 py-1 text-sm text-vpv-text placeholder:text-vpv-text-muted"
            />
          </label>
          <SeasonSelector />
        </div>
      </div>

      {jornada && (
        <p className="text-sm text-vpv-text-muted">
          Mostrando plantillas a fecha de jornada {jornada}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.squads.map((squad) => (
          <Link
            key={squad.participant_id}
            href={`/plantillas/${squad.participant_id}${jornada ? `?jornada=${jornada}` : ""}`}
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
