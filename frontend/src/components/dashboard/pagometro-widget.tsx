import Link from "next/link";
import type { ParticipantBalance } from "@/types";

const RANK_STYLES: Record<number, { badge: string }> = {
  1: { badge: "bg-vpv-gold text-black" },
  2: { badge: "bg-gray-300 text-black" },
  3: { badge: "bg-amber-700 text-white" },
};

interface PagometroEntry {
  participant_id: number;
  display_name: string;
  amount: number;
}

function computePagometro(balances: ParticipantBalance[]): PagometroEntry[] {
  return balances
    .map((b) => ({
      participant_id: b.participant_id,
      display_name: b.display_name,
      amount: b.net_balance - b.initial_fee - b.draft_fees,
    }))
    .sort((a, b) => b.amount - a.amount);
}

export function PagometroWidget({
  balances,
}: {
  balances: ParticipantBalance[];
}) {
  const entries = computePagometro(balances);
  if (entries.length === 0) return null;

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Pagometro
        </h2>
        <Link
          href="/economia"
          className="text-xs text-vpv-accent transition-colors hover:text-vpv-accent-hover"
        >
          Ver economia &rarr;
        </Link>
      </div>

      <div className="mt-3 space-y-2">
        {entries.map((entry, idx) => {
          const rank = idx + 1;
          const style = RANK_STYLES[rank] ?? {
            badge: "bg-vpv-border text-vpv-text-muted",
          };

          return (
            <div
              key={entry.participant_id}
              className="flex items-center gap-3"
            >
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${style.badge}`}
              >
                {rank}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className={`truncate font-medium ${rank === 1 ? "text-vpv-accent" : "text-vpv-text"}`}
                >
                  {entry.display_name}
                </p>
              </div>
              <span
                className={`text-sm font-bold tabular-nums ${
                  entry.amount > 0
                    ? "text-red-400"
                    : entry.amount < 0
                      ? "text-green-400"
                      : "text-vpv-text-muted"
                }`}
              >
                {entry.amount > 0 ? "+" : ""}
                {entry.amount.toFixed(0)} &euro;
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
