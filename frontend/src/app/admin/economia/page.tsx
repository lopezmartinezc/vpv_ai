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
  initial_fee: "Cuota",
  weekly_payment: "Semanal",
  winter_draft_fee: "Draft inv.",
  prize: "Premio",
  manual_adjustment: "Ajuste",
  penalty: "Penalizacion",
};

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

  // Transaction detail
  const [selectedParticipant, setSelectedParticipant] = useState<number | null>(
    null,
  );
  const [transactions, setTransactions] = useState<TransactionEntry[]>([]);
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
      setSelectedParticipant(null);
      setTransactions([]);
    }
  }, [selectedSeasonId, fetchBalances]);

  async function handleViewTransactions(participantId: number) {
    if (selectedParticipant === participantId) {
      setSelectedParticipant(null);
      setTransactions([]);
      return;
    }
    setSelectedParticipant(participantId);
    setTxLoading(true);
    try {
      const data = await apiClient.get<{
        transactions: TransactionEntry[];
      }>(`/economy/${selectedSeasonId}/${participantId}`);
      setTransactions(data.transactions);
    } catch {
      // handled
    } finally {
      setTxLoading(false);
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
      if (selectedParticipant === Number(formParticipant)) {
        await handleViewTransactions(selectedParticipant);
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
    if (!selectedSeasonId || !selectedParticipant) return;
    try {
      await apiClient.delete(
        `/economy/admin/${selectedSeasonId}/transaction/${txId}`,
      );
      setTransactions((prev) => prev.filter((t) => t.id !== txId));
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

      {/* Balances table */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Balances ({balances.length})
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
                <th className="px-4 py-2">Participante</th>
                <th className="px-4 py-2 text-right">Cuota</th>
                <th className="px-4 py-2 text-right">Semanal</th>
                <th className="px-4 py-2 text-right">Draft</th>
                <th className="px-4 py-2 text-right">Balance</th>
                <th className="px-4 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {balances.map((b) => (
                <tr
                  key={b.participant_id}
                  className={`border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50 ${
                    selectedParticipant === b.participant_id
                      ? "bg-vpv-bg/30"
                      : ""
                  }`}
                >
                  <td className="px-4 py-2 font-medium text-vpv-text">
                    {b.display_name}
                  </td>
                  <td className="px-4 py-2 text-right text-vpv-text-muted">
                    {b.initial_fee.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right text-vpv-text-muted">
                    {b.weekly_total.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right text-vpv-text-muted">
                    {b.draft_fees.toFixed(2)}
                  </td>
                  <td
                    className={`px-4 py-2 text-right font-medium ${
                      b.net_balance >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {b.net_balance.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() =>
                        handleViewTransactions(b.participant_id)
                      }
                      className="rounded border border-vpv-border px-2 py-1 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text"
                    >
                      {selectedParticipant === b.participant_id
                        ? "Cerrar"
                        : "Ver"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Transaction detail */}
      {selectedParticipant !== null && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
          <div className="border-b border-vpv-border px-4 py-3">
            <h2 className="font-semibold text-vpv-text">
              Transacciones —{" "}
              {balances.find((b) => b.participant_id === selectedParticipant)
                ?.display_name ?? ""}
            </h2>
          </div>
          {txLoading ? (
            <div className="px-4 py-3">
              <div className="h-20 animate-pulse rounded bg-vpv-border" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-vpv-border bg-vpv-bg text-left text-xs text-vpv-text-muted">
                    <th className="px-4 py-2">Tipo</th>
                    <th className="px-4 py-2 text-right">Cantidad</th>
                    <th className="px-4 py-2">Descripcion</th>
                    <th className="px-4 py-2">Jornada</th>
                    <th className="px-4 py-2">Fecha</th>
                    <th className="px-4 py-2 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr
                      key={tx.id}
                      className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                    >
                      <td className="px-4 py-1.5 text-vpv-text">
                        {TX_TYPE_LABELS[tx.type] ?? tx.type}
                      </td>
                      <td
                        className={`px-4 py-1.5 text-right font-medium ${
                          tx.amount >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {tx.amount.toFixed(2)}
                      </td>
                      <td className="px-4 py-1.5 text-vpv-text-muted">
                        {tx.description ?? "—"}
                      </td>
                      <td className="px-4 py-1.5 text-vpv-text-muted">
                        {tx.matchday_number !== null
                          ? `J${tx.matchday_number}`
                          : "—"}
                      </td>
                      <td className="px-4 py-1.5 text-xs text-vpv-text-muted">
                        {new Date(tx.created_at).toLocaleDateString("es-ES")}
                      </td>
                      <td className="px-4 py-1.5 text-right">
                        <button
                          onClick={() => handleDeleteTransaction(tx.id)}
                          className="rounded px-2 py-0.5 text-xs text-red-400 transition-colors hover:bg-red-600/20"
                        >
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))}
                  {transactions.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-3 text-center text-sm text-vpv-text-muted"
                      >
                        Sin transacciones
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
