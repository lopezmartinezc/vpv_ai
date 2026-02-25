import type { TransactionEntry } from "@/types";

const TYPE_LABELS: Record<string, string> = {
  initial_fee: "Cuota inicial",
  weekly_payment: "Pago semanal",
  winter_draft_fee: "Draft invierno",
  prize: "Premio",
  adjustment: "Ajuste",
};

export function TransactionList({
  transactions,
}: {
  transactions: TransactionEntry[];
}) {
  return (
    <>
      {/* Mobile: Cards */}
      <div className="space-y-2 md:hidden">
        {transactions.map((tx) => (
          <div
            key={tx.id}
            className="flex items-center justify-between rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3"
          >
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-vpv-text">
                {TYPE_LABELS[tx.type] ?? tx.type}
              </p>
              <p className="truncate text-xs text-vpv-text-muted">
                {tx.description ?? "–"}
                {tx.matchday_number != null && ` \u00b7 J${tx.matchday_number}`}
              </p>
            </div>
            <span
              className={`ml-3 text-base font-bold tabular-nums ${
                tx.amount < 0 ? "text-green-400" : "text-vpv-text"
              }`}
            >
              {tx.amount.toFixed(2)} &euro;
            </span>
          </div>
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden overflow-x-auto rounded-lg border border-vpv-card-border md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="px-4 py-2">Tipo</th>
              <th className="px-4 py-2">Descripcion</th>
              <th className="px-4 py-2">Jornada</th>
              <th className="px-4 py-2 text-right">Importe</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => (
              <tr
                key={tx.id}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-accent/5"
              >
                <td className="px-4 py-2 text-vpv-text">
                  {TYPE_LABELS[tx.type] ?? tx.type}
                </td>
                <td className="px-4 py-2 text-vpv-text-muted">
                  {tx.description ?? "–"}
                </td>
                <td className="px-4 py-2 text-vpv-text-muted">
                  {tx.matchday_number ?? "–"}
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
    </>
  );
}
