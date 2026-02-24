"use client";

import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { EconomyResponse } from "@/types";

export default function EconomiaPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<EconomyResponse>(
    selectedSeason ? `/economy/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-vpv-text-muted">Cargando economia...</p>
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
      <h1 className="text-2xl font-bold text-vpv-text">
        Economia {selectedSeason?.name}
      </h1>

      <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="px-4 py-3">Participante</th>
              <th className="px-4 py-3 text-right">Cuota</th>
              <th className="px-4 py-3 text-right">Semanal</th>
              <th className="hidden px-4 py-3 text-right sm:table-cell">
                Draft inv.
              </th>
              <th className="px-4 py-3 text-right font-bold">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.balances.map((b) => (
              <Link
                key={b.participant_id}
                href={`/economia/${b.participant_id}`}
                className="contents"
              >
                <tr className="border-b border-vpv-border transition-colors last:border-0 hover:bg-vpv-accent/5 cursor-pointer">
                  <td className="px-4 py-3 font-medium text-vpv-text">
                    {b.display_name}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                    {b.initial_fee.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                    {b.weekly_total.toFixed(2)}
                  </td>
                  <td className="hidden px-4 py-3 text-right tabular-nums text-vpv-text-muted sm:table-cell">
                    {b.draft_fees.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right font-bold tabular-nums text-vpv-text">
                    {b.net_balance.toFixed(2)} &euro;
                  </td>
                </tr>
              </Link>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
