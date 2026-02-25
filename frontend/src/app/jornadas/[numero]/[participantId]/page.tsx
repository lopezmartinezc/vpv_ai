"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { PlayerList } from "@/components/matchdays/player-list";
import { SkeletonTable } from "@/components/ui/skeleton";
import type { LineupDetailResponse } from "@/types";

export default function LineupDetailPage() {
  const params = useParams<{ numero: string; participantId: string }>();
  const numero = Number(params.numero);
  const participantId = Number(params.participantId);
  const { selectedSeason, loading: seasonLoading } = useSeason();

  const { data, loading } = useFetch<LineupDetailResponse>(
    selectedSeason
      ? `/matchdays/${selectedSeason.id}/${numero}/lineup/${participantId}`
      : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-6">
        <div className="h-4 w-60 animate-pulse rounded bg-vpv-border" />
        <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={11} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar la alineacion.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-2 text-sm text-vpv-text-muted">
        <Link
          href="/jornadas"
          className="transition-colors hover:text-vpv-text"
        >
          Jornadas
        </Link>
        <span>/</span>
        <Link
          href={`/jornadas/${numero}`}
          className="transition-colors hover:text-vpv-text"
        >
          Jornada {numero}
        </Link>
        <span>/</span>
        <span className="text-vpv-text">{data.display_name}</span>
      </nav>

      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-vpv-text">
          {data.display_name}
        </h1>
        <div className="text-right">
          <p className="text-3xl font-bold tabular-nums text-vpv-accent">
            {data.total_points}
          </p>
          <p className="text-xs text-vpv-text-muted">{data.formation}</p>
        </div>
      </div>

      <PlayerList players={data.players} />
    </div>
  );
}
