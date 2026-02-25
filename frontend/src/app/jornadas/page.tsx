"use client";

import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SeasonSelector } from "@/components/layout/season-selector";
import type { MatchdayListResponse } from "@/types";

export default function JornadasPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<MatchdayListResponse>(
    selectedSeason ? `/matchdays/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-vpv-border" />
        <div className="grid grid-cols-4 gap-3 sm:grid-cols-6 lg:grid-cols-8">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-lg bg-vpv-border"
            />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudieron cargar las jornadas.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">
          Jornadas {selectedSeason?.name}
        </h1>
        <SeasonSelector />
      </div>

      <div className="grid grid-cols-4 gap-3 sm:grid-cols-6 lg:grid-cols-8">
        {data.matchdays.map((md) => (
          <Link
            key={md.number}
            href={`/jornadas/${md.number}`}
            className={`flex flex-col items-center rounded-lg border p-3 text-center transition-colors hover:border-vpv-accent ${
              md.counts
                ? "border-vpv-card-border bg-vpv-card"
                : "border-vpv-border bg-vpv-bg opacity-60"
            }`}
          >
            <span className="text-lg font-bold text-vpv-text">
              {md.number}
            </span>
            <span className="text-xs capitalize text-vpv-text-muted">
              {md.status}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
