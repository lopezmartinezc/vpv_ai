"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { TransactionList } from "@/components/economy/transaction-list";
import { SkeletonTable } from "@/components/ui/skeleton";
import type { ParticipantEconomyResponse } from "@/types";

export default function ParticipantEconomyPage() {
  const { participantId } = useParams<{ participantId: string }>();
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<ParticipantEconomyResponse>(
    selectedSeason && participantId
      ? `/economy/${selectedSeason.id}/${participantId}`
      : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-4 w-32 animate-pulse rounded bg-vpv-border" />
        <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={6} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudieron cargar las transacciones.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href="/economia"
          className="text-vpv-text-muted transition-colors hover:text-vpv-text"
        >
          Economia
        </Link>
        <span className="text-vpv-text-muted">/</span>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-vpv-text">
          {data.display_name}
        </h1>
        <span className="text-xl font-bold tabular-nums text-vpv-accent">
          {data.net_balance.toFixed(2)} &euro;
        </span>
      </div>

      <p className="text-sm text-vpv-text-muted">
        {data.transactions.length} transacciones
      </p>

      <TransactionList transactions={data.transactions} />
    </div>
  );
}
