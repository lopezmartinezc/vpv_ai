"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { ParticipantEconomyResponse } from "@/types";

const TYPE_LABELS: Record<string, string> = {
  initial_fee: "Cuota inicial",
  weekly_payment: "Pago semanal",
  winter_draft_fee: "Draft invierno",
  prize: "Premio",
  adjustment: "Ajuste",
};

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
      <div className="flex items-center justify-center py-20">
        <p className="text-vpv-text-muted">Cargando transacciones...</p>
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

      <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="px-4 py-2">Tipo</th>
              <th className="px-4 py-2">Descripcion</th>
              <th className="hidden px-4 py-2 sm:table-cell">Jornada</th>
              <th className="px-4 py-2 text-right">Importe</th>
            </tr>
          </thead>
          <tbody>
            {data.transactions.map((tx) => (
              <tr
                key={tx.id}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-accent/5"
              >
                <td className="px-4 py-2 text-vpv-text">
                  {TYPE_LABELS[tx.type] ?? tx.type}
                </td>
                <td className="px-4 py-2 text-vpv-text-muted">
                  {tx.description ?? "-"}
                </td>
                <td className="hidden px-4 py-2 text-vpv-text-muted sm:table-cell">
                  {tx.matchday_number ?? "-"}
                </td>
                <td
                  className={`px-4 py-2 text-right font-bold tabular-nums ${
                    tx.amount < 0 ? "text-green-400" : "text-vpv-text"
                  }`}
                >
                  {tx.amount.toFixed(2)} &euro;
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
