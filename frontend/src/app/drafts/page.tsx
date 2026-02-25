"use client";

import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SeasonSelector } from "@/components/layout/season-selector";
import type { DraftListResponse } from "@/types";

const PHASE_LABELS: Record<string, string> = {
  preseason: "Pretemporada",
  winter: "Invierno",
};

const TYPE_LABELS: Record<string, string> = {
  snake: "Serpiente",
  linear: "Lineal",
};

export default function DraftsPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<DraftListResponse>(
    selectedSeason ? `/drafts/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-lg bg-vpv-border"
            />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudieron cargar los drafts.
      </div>
    );
  }

  if (data.drafts.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-vpv-text">
            Drafts {selectedSeason?.name}
          </h1>
          <SeasonSelector />
        </div>
        <p className="text-vpv-text-muted">
          No hay drafts registrados para esta temporada.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">
          Drafts {selectedSeason?.name}
        </h1>
        <SeasonSelector />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {data.drafts.map((draft) => (
          <Link
            key={draft.id}
            href={`/drafts/${draft.phase}`}
            className="rounded-lg border border-vpv-card-border bg-vpv-card p-5 transition-colors hover:border-vpv-accent"
          >
            <h2 className="text-lg font-semibold text-vpv-text">
              {PHASE_LABELS[draft.phase] ?? draft.phase}
            </h2>
            <div className="mt-2 space-y-1 text-sm text-vpv-text-muted">
              <p>
                Tipo: {TYPE_LABELS[draft.draft_type] ?? draft.draft_type}
              </p>
              <p>Picks: {draft.total_picks}</p>
              <p className="capitalize">Estado: {draft.status}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
