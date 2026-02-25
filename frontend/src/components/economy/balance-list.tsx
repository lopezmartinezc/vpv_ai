import Link from "next/link";
import type { ParticipantBalance } from "@/types";

export function BalanceList({
  balances,
}: {
  balances: ParticipantBalance[];
}) {
  return (
    <>
      {/* Mobile: Cards */}
      <div className="space-y-2 md:hidden">
        {balances.map((b) => (
          <Link
            key={b.participant_id}
            href={`/economia/${b.participant_id}`}
            className="block rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3 transition-colors hover:border-vpv-accent"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-vpv-text">
                {b.display_name}
              </span>
              <span className="text-lg font-bold tabular-nums text-vpv-text">
                {b.net_balance.toFixed(2)} &euro;
              </span>
            </div>
            <div className="mt-1 flex gap-3 text-xs text-vpv-text-muted">
              <span>Cuota {b.initial_fee.toFixed(0)}</span>
              <span>Semanal {b.weekly_total.toFixed(0)}</span>
              {b.draft_fees > 0 && (
                <span>Draft {b.draft_fees.toFixed(0)}</span>
              )}
            </div>
          </Link>
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden overflow-x-auto rounded-lg border border-vpv-card-border md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="px-4 py-3">Participante</th>
              <th className="px-4 py-3 text-right">Cuota</th>
              <th className="px-4 py-3 text-right">Semanal</th>
              <th className="px-4 py-3 text-right">Draft inv.</th>
              <th className="px-4 py-3 text-right font-bold">Total</th>
            </tr>
          </thead>
          <tbody>
            {balances.map((b) => (
              <tr
                key={b.participant_id}
                className="border-b border-vpv-border transition-colors last:border-0 hover:bg-vpv-accent/5"
              >
                <td className="px-4 py-3 font-medium text-vpv-text">
                  <Link
                    href={`/economia/${b.participant_id}`}
                    className="transition-colors hover:text-vpv-accent"
                  >
                    {b.display_name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {b.initial_fee.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {b.weekly_total.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-vpv-text-muted">
                  {b.draft_fees.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-right font-bold tabular-nums text-vpv-text">
                  {b.net_balance.toFixed(2)} &euro;
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
