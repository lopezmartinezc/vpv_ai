"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface SeasonSummary {
  id: number;
  name: string;
  status: string;
}

interface ParticipantBalance {
  participant_id: number;
  display_name: string;
  initial_fee: number;
  weekly_total: number;
  draft_fees: number;
  net_balance: number;
}

interface TransactionEntry {
  id: number;
  type: string;
  amount: number;
  description: string | null;
  matchday_number: number | null;
  created_at: string;
}

const TX_TYPES = [
  { value: "manual_adjustment", label: "Ajuste manual" },
  { value: "initial_fee", label: "Cuota inicial" },
  { value: "weekly_payment", label: "Pago semanal" },
  { value: "winter_draft_fee", label: "Cuota draft invierno" },
  { value: "prize", label: "Premio" },
  { value: "penalty", label: "Penalizacion" },
];

const TX_TYPE_LABELS: Record<string, string> = {
  initial_fee: "Cuota inicial",
  weekly_payment: "Pago semanal",
  winter_draft_fee: "Draft invierno",
  prize: "Premio",
  manual_adjustment: "Ajuste",
  penalty: "Penalizacion",
};

/** Sort transactions into logical order: inicio, jornadas, draft inv, otros */
function sortTransactions(txs: TransactionEntry[]): {
  label: string;
  tx: TransactionEntry;
}[] {
  function txSortKey(tx: TransactionEntry): { order: number; label: string } {
    if (tx.type === "initial_fee")
      return { order: 0, label: "Inicio temporada" };
    if (tx.type === "winter_draft_fee")
      return { order: 0.5, label: "Draft invierno" };
    if (tx.matchday_number !== null)
      return { order: tx.matchday_number, label: `J${tx.matchday_number}` };
    return { order: 999, label: "Otros" };
  }

  const items = txs.map((tx) => ({ ...txSortKey(tx), tx }));
  items.sort((a, b) => a.order - b.order);

  // Add group label only on first item of each group
  let lastLabel = "";
  return items.map((item) => {
    const showLabel = item.label !== lastLabel;
    lastLabel = item.label;
    return { label: showLabel ? item.label : "", tx: item.tx };
  });
}

export default function AdminEconomiaPage() {
  const [seasons, setSeasons] = useState<SeasonSummary[]>([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);
  const [balances, setBalances] = useState<ParticipantBalance[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  // Create form
  const [showForm, setShowForm] = useState(false);
  const [formParticipant, setFormParticipant] = useState("");
  const [formType, setFormType] = useState("manual_adjustment");
  const [formAmount, setFormAmount] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formSaving, setFormSaving] = useState(false);

  // Transaction detail — per-participant accordion
  const [expandedParticipant, setExpandedParticipant] = useState<number | null>(
    null,
  );
  const [participantTxs, setParticipantTxs] = useState<
    Map<number, TransactionEntry[]>
  >(new Map());
  const [txLoading, setTxLoading] = useState(false);

  const fetchSeasons = useCallback(async () => {
    try {
      const data = await apiClient.get<SeasonSummary[]>("/seasons");
      setSeasons(data);
      if (data.length > 0 && selectedSeasonId === null) {
        const active = data.find((s) => s.status === "active") ?? data[0];
        setSelectedSeasonId(active.id);
      }
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  }, [selectedSeasonId]);

  const fetchBalances = useCallback(async (seasonId: number) => {
    try {
      const data = await apiClient.get<{
        balances: ParticipantBalance[];
      }>(`/economy/${seasonId}`);
      setBalances(data.balances);
    } catch {
      // handled
    }
  }, []);

  useEffect(() => {
    fetchSeasons();
  }, [fetchSeasons]);

  useEffect(() => {
    if (selectedSeasonId !== null) {
      fetchBalances(selectedSeasonId);
      setExpandedParticipant(null);
      setParticipantTxs(new Map());
    }
  }, [selectedSeasonId, fetchBalances]);

  async function handleToggleParticipant(participantId: number) {
    if (expandedParticipant === participantId) {
      setExpandedParticipant(null);
      return;
    }
    setExpandedParticipant(participantId);
    // Fetch if not cached
    if (!participantTxs.has(participantId)) {
      setTxLoading(true);
      try {
        const data = await apiClient.get<{
          transactions: TransactionEntry[];
        }>(`/economy/${selectedSeasonId}/${participantId}`);
        setParticipantTxs((prev) =>
          new Map(prev).set(participantId, data.transactions),
        );
      } catch {
        // handled
      } finally {
        setTxLoading(false);
      }
    }
  }

  async function handleCreateTransaction() {
    if (!selectedSeasonId || !formParticipant || !formAmount) return;
    setFormSaving(true);
    try {
      await apiClient.post(`/economy/admin/${selectedSeasonId}/transaction`, {
        participant_id: Number(formParticipant),
        type: formType,
        amount: Number(formAmount),
        description: formDescription || null,
      });
      await fetchBalances(selectedSeasonId);
      // Invalidate cached txs for this participant so next expand refetches
      const pid = Number(formParticipant);
      setParticipantTxs((prev) => {
        const next = new Map(prev);
        next.delete(pid);
        return next;
      });
      // If expanded, refetch immediately
      if (expandedParticipant === pid) {
        const data = await apiClient.get<{
          transactions: TransactionEntry[];
        }>(`/economy/${selectedSeasonId}/${pid}`);
        setParticipantTxs((prev) =>
          new Map(prev).set(pid, data.transactions),
        );
      }
      setShowForm(false);
      setFormParticipant("");
      setFormAmount("");
      setFormDescription("");
      showMsg("Transaccion creada");
    } catch {
      showMsg("Error al crear transaccion");
    } finally {
      setFormSaving(false);
    }
  }

  async function handleDeleteTransaction(txId: number) {
    if (!selectedSeasonId || !expandedParticipant) return;
    try {
      await apiClient.delete(
        `/economy/admin/${selectedSeasonId}/transaction/${txId}`,
      );
      // Update cached txs
      setParticipantTxs((prev) => {
        const next = new Map(prev);
        const txs = next.get(expandedParticipant);
        if (txs) next.set(expandedParticipant, txs.filter((t) => t.id !== txId));
        return next;
      });
      await fetchBalances(selectedSeasonId);
      showMsg("Transaccion eliminada");
    } catch {
      showMsg("Error al eliminar");
    }
  }

  function showMsg(msg: string) {
    setMessage(msg);
    setTimeout(() => setMessage(null), 3000);
  }

  if (loading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-12 animate-pulse rounded-lg bg-vpv-border"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-vpv-text-muted">Temporada:</label>
        <select
          value={selectedSeasonId ?? ""}
          onChange={(e) => setSelectedSeasonId(Number(e.target.value))}
          className="rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text"
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80"
        >
          {showForm ? "Cancelar" : "Nueva transaccion"}
        </button>
        {message && (
          <span className="text-xs text-vpv-text-muted">{message}</span>
        )}
      </div>

      {/* Create transaction form */}
      {showForm && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3">
          <h3 className="mb-3 text-sm font-semibold text-vpv-text">
            Nueva transaccion
          </h3>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs text-vpv-text-muted">
                Participante
              </label>
              <select
                value={formParticipant}
                onChange={(e) => setFormParticipant(e.target.value)}
                className="rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
              >
                <option value="">Seleccionar...</option>
                {balances.map((b) => (
                  <option key={b.participant_id} value={b.participant_id}>
                    {b.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-vpv-text-muted">
                Tipo
              </label>
              <select
                value={formType}
                onChange={(e) => setFormType(e.target.value)}
                className="rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
              >
                {TX_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-vpv-text-muted">
                Cantidad
              </label>
              <input
                type="number"
                step="0.01"
                value={formAmount}
                onChange={(e) => setFormAmount(e.target.value)}
                placeholder="ej: -5.00"
                className="w-28 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-vpv-text-muted">
                Descripcion
              </label>
              <input
                type="text"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Opcional"
                className="w-40 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
              />
            </div>
            <button
              onClick={handleCreateTransaction}
              disabled={formSaving || !formParticipant || !formAmount}
              className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
            >
              {formSaving ? "Creando..." : "Crear"}
            </button>
          </div>
        </div>
      )}

      {/* Balances — accordion per participant */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Balances ({balances.length})
          </h2>
        </div>
        <div>
          {balances.map((b) => {
            const isOpen = expandedParticipant === b.participant_id;
            const txs = participantTxs.get(b.participant_id);
            return (
              <div
                key={b.participant_id}
                className="border-b border-vpv-border last:border-0"
              >
                {/* Participant header row — clickable */}
                <button
                  type="button"
                  onClick={() => handleToggleParticipant(b.participant_id)}
                  className={`flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-vpv-bg/50 ${
                    isOpen ? "bg-vpv-bg/30" : ""
                  }`}
                >
                  <svg
                    className={`h-3.5 w-3.5 shrink-0 text-vpv-text-muted transition-transform ${isOpen ? "rotate-90" : ""}`}
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-vpv-text">
                    {b.display_name}
                  </span>
                  <span className="hidden text-xs text-vpv-text-muted sm:inline">
                    {b.initial_fee.toFixed(2)}
                  </span>
                  <span className="hidden text-xs text-vpv-text-muted sm:inline">
                    {b.weekly_total.toFixed(2)}
                  </span>
                  <span className="hidden text-xs text-vpv-text-muted sm:inline">
                    {b.draft_fees.toFixed(2)}
                  </span>
                  <span
                    className={`w-16 text-right text-sm font-medium tabular-nums ${
                      b.net_balance >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {b.net_balance.toFixed(2)}
                  </span>
                </button>

                {/* Expanded: one line per transaction */}
                {isOpen && (
                  <div className="border-t border-vpv-border/50 bg-vpv-bg/20">
                    {txLoading && !txs ? (
                      <div className="px-6 py-3">
                        <div className="h-8 animate-pulse rounded bg-vpv-border" />
                      </div>
                    ) : txs && txs.length === 0 ? (
                      <p className="px-6 py-2 text-center text-xs text-vpv-text-muted">
                        Sin transacciones
                      </p>
                    ) : txs ? (
                      <div className="divide-y divide-vpv-border/20">
                        {sortTransactions(txs).map(({ label, tx }) => (
                          <div
                            key={tx.id}
                            className="flex items-center gap-2 py-1 pl-8 pr-4 text-xs hover:bg-vpv-bg/40"
                          >
                            {label ? (
                              <span className="w-28 shrink-0 truncate font-semibold text-vpv-text-muted">
                                {label}
                              </span>
                            ) : (
                              <span className="w-28 shrink-0" />
                            )}
                            <span className="w-20 shrink-0 text-vpv-text-muted">
                              {TX_TYPE_LABELS[tx.type] ?? tx.type}
                            </span>
                            <span
                              className={`w-16 shrink-0 text-right font-medium tabular-nums ${
                                tx.amount >= 0
                                  ? "text-green-400"
                                  : "text-red-400"
                              }`}
                            >
                              {tx.amount.toFixed(2)}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-vpv-text-muted">
                              {tx.description ?? ""}
                            </span>
                            <span className="w-20 shrink-0 text-right text-[11px] text-vpv-text-muted">
                              {new Date(tx.created_at).toLocaleDateString(
                                "es-ES",
                              )}
                            </span>
                            <button
                              onClick={() => handleDeleteTransaction(tx.id)}
                              className="shrink-0 rounded px-1.5 py-0.5 text-[11px] text-red-400 transition-colors hover:bg-red-600/20"
                            >
                              Eliminar
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
