"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { PicksList } from "@/components/drafts/picks-list";
import { SkeletonTable } from "@/components/ui/skeleton";
import type { DraftDetailResponse } from "@/types";

const PHASE_LABELS: Record<string, string> = {
  preseason: "Pretemporada",
  winter: "Invierno",
};

export default function DraftDetailPage() {
  const { phase } = useParams<{ phase: string }>();
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<DraftDetailResponse>(
    selectedSeason && phase
      ? `/drafts/${selectedSeason.id}/${phase}`
      : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-4 w-20 animate-pulse rounded bg-vpv-border" />
        <div className="h-8 w-48 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={10} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar el draft.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href="/drafts"
          className="text-vpv-text-muted transition-colors hover:text-vpv-text"
        >
          Drafts
        </Link>
        <span className="text-vpv-text-muted">/</span>
      </div>

      <h1 className="text-2xl font-bold text-vpv-text">
        Draft {PHASE_LABELS[data.phase] ?? data.phase}
      </h1>

      <p className="text-sm text-vpv-text-muted">
        {data.picks.length} picks &middot;{" "}
        {data.participants.length} participantes
      </p>

      <PicksList picks={data.picks} />
    </div>
  );
}
