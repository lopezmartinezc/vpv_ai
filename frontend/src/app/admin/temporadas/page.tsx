"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface Season {
  id: number;
  name: string;
  status: string;
  matchday_start: number;
  matchday_end: number | null;
  matchday_current: number;
  matchday_winter: number | null;
  matchday_scanned: number;
  draft_pool_size: number;
  lineup_deadline_min: number;
  total_participants: number;
}

interface ScoringRule {
  id: number;
  rule_key: string;
  position: string | null;
  value: number;
  description: string | null;
}

interface SeasonSummary {
  id: number;
  name: string;
  status: string;
  matchday_current: number;
  total_participants: number;
}

const STATUS_LABELS: Record<string, string> = {
  setup: "Configuracion",
  active: "Activa",
  finished: "Finalizada",
};

export default function AdminTemporadasPage() {
  const [seasons, setSeasons] = useState<SeasonSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [season, setSeason] = useState<Season | null>(null);
  const [rules, setRules] = useState<ScoringRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingRules, setSavingRules] = useState(false);
  const [editedRules, setEditedRules] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  // Editable season fields
  const [editStatus, setEditStatus] = useState("");
  const [editMatchdayCurrent, setEditMatchdayCurrent] = useState("");
  const [editMatchdayEnd, setEditMatchdayEnd] = useState("");
  const [editMatchdayWinter, setEditMatchdayWinter] = useState("");
  const [editLineupDeadline, setEditLineupDeadline] = useState("");
  const [editDraftPool, setEditDraftPool] = useState("");

  const fetchSeasons = useCallback(async () => {
    try {
      const data = await apiClient.get<SeasonSummary[]>("/seasons");
      setSeasons(data);
      if (data.length > 0 && selectedId === null) {
        const active = data.find((s) => s.status === "active") ?? data[0];
        setSelectedId(active.id);
      }
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  const fetchSeasonDetail = useCallback(async (id: number) => {
    try {
      const [detail, scoringRules] = await Promise.all([
        apiClient.get<Season>(`/seasons/${id}`),
        apiClient.get<ScoringRule[]>(`/seasons/${id}/scoring-rules`),
      ]);
      setSeason(detail);
      setRules(scoringRules);
      setEditedRules({});
      // Populate edit fields
      setEditStatus(detail.status);
      setEditMatchdayCurrent(String(detail.matchday_current));
      setEditMatchdayEnd(detail.matchday_end !== null ? String(detail.matchday_end) : "");
      setEditMatchdayWinter(detail.matchday_winter !== null ? String(detail.matchday_winter) : "");
      setEditLineupDeadline(String(detail.lineup_deadline_min));
      setEditDraftPool(String(detail.draft_pool_size));
    } catch {
      // handled
    }
  }, []);

  useEffect(() => {
    fetchSeasons();
  }, [fetchSeasons]);

  useEffect(() => {
    if (selectedId !== null) {
      fetchSeasonDetail(selectedId);
    }
  }, [selectedId, fetchSeasonDetail]);

  async function handleSaveSeason() {
    if (!selectedId || !season) return;
    setSaving(true);
    setMessage(null);
    try {
      const body: Record<string, unknown> = {};
      if (editStatus !== season.status) body.status = editStatus;
      if (editMatchdayCurrent !== String(season.matchday_current))
        body.matchday_current = Number(editMatchdayCurrent);
      if (editMatchdayEnd !== (season.matchday_end !== null ? String(season.matchday_end) : ""))
        body.matchday_end = editMatchdayEnd ? Number(editMatchdayEnd) : null;
      if (editMatchdayWinter !== (season.matchday_winter !== null ? String(season.matchday_winter) : ""))
        body.matchday_winter = editMatchdayWinter ? Number(editMatchdayWinter) : null;
      if (editLineupDeadline !== String(season.lineup_deadline_min))
        body.lineup_deadline_min = Number(editLineupDeadline);
      if (editDraftPool !== String(season.draft_pool_size))
        body.draft_pool_size = Number(editDraftPool);

      if (Object.keys(body).length === 0) {
        setMessage("Sin cambios");
        return;
      }

      const updated = await apiClient.put<Season>(
        `/seasons/admin/${selectedId}`,
        body,
      );
      setSeason(updated);
      setMessage("Temporada actualizada");
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage("Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveRules() {
    if (!selectedId) return;
    const changed = Object.entries(editedRules)
      .filter(([id, val]) => {
        const rule = rules.find((r) => r.id === Number(id));
        return rule && String(rule.value) !== val;
      })
      .map(([id, val]) => ({ id: Number(id), value: Number(val) }));

    if (changed.length === 0) {
      setMessage("Sin cambios en reglas");
      return;
    }

    setSavingRules(true);
    setMessage(null);
    try {
      const updated = await apiClient.put<ScoringRule[]>(
        `/seasons/admin/${selectedId}/scoring-rules`,
        { rules: changed },
      );
      setRules(updated);
      setEditedRules({});
      setMessage(`${changed.length} regla(s) actualizada(s)`);
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage("Error al guardar reglas");
    } finally {
      setSavingRules(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 py-4">
        <div className="h-48 animate-pulse rounded-lg bg-vpv-border" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Season selector */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-vpv-text-muted">Temporada:</label>
        <select
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(Number(e.target.value))}
          className="rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text"
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({STATUS_LABELS[s.status] ?? s.status})
            </option>
          ))}
        </select>
      </div>

      {season && (
        <>
          {/* Season config */}
          <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
            <div className="border-b border-vpv-border px-4 py-3">
              <h2 className="font-semibold text-vpv-text">
                Configuracion — {season.name}
              </h2>
            </div>
            <div className="space-y-3 px-4 py-3">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Estado
                  </label>
                  <select
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value)}
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  >
                    <option value="setup">Configuracion</option>
                    <option value="active">Activa</option>
                    <option value="finished">Finalizada</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Jornada actual
                  </label>
                  <input
                    type="number"
                    value={editMatchdayCurrent}
                    onChange={(e) => setEditMatchdayCurrent(e.target.value)}
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Jornada final
                  </label>
                  <input
                    type="number"
                    value={editMatchdayEnd}
                    onChange={(e) => setEditMatchdayEnd(e.target.value)}
                    placeholder="—"
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Jornada invierno
                  </label>
                  <input
                    type="number"
                    value={editMatchdayWinter}
                    onChange={(e) => setEditMatchdayWinter(e.target.value)}
                    placeholder="—"
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Deadline (min)
                  </label>
                  <input
                    type="number"
                    value={editLineupDeadline}
                    onChange={(e) => setEditLineupDeadline(e.target.value)}
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Pool draft
                  </label>
                  <input
                    type="number"
                    value={editDraftPool}
                    onChange={(e) => setEditDraftPool(e.target.value)}
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3 text-xs text-vpv-text-muted">
                <span>Inicio: J{season.matchday_start}</span>
                <span>Scanned: J{season.matchday_scanned}</span>
                <span>Participantes: {season.total_participants}</span>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleSaveSeason}
                  disabled={saving}
                  className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
                >
                  {saving ? "Guardando..." : "Guardar cambios"}
                </button>
                {message && (
                  <span className="text-xs text-vpv-text-muted">{message}</span>
                )}
              </div>
            </div>
          </div>

          {/* Scoring Rules */}
          <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
            <div className="border-b border-vpv-border px-4 py-3">
              <h2 className="font-semibold text-vpv-text">
                Reglas de puntuacion ({rules.length})
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
                    <th className="px-4 py-2">Regla</th>
                    <th className="px-4 py-2">Posicion</th>
                    <th className="px-4 py-2">Descripcion</th>
                    <th className="px-4 py-2 text-right">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr
                      key={rule.id}
                      className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                    >
                      <td className="px-4 py-2 font-medium text-vpv-text">
                        {rule.rule_key}
                      </td>
                      <td className="px-4 py-2 text-vpv-text-muted">
                        {rule.position ?? "Todas"}
                      </td>
                      <td className="px-4 py-2 text-vpv-text-muted">
                        {rule.description ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <input
                          type="number"
                          step="0.01"
                          value={
                            editedRules[rule.id] !== undefined
                              ? editedRules[rule.id]
                              : String(rule.value)
                          }
                          onChange={(e) =>
                            setEditedRules((prev) => ({
                              ...prev,
                              [rule.id]: e.target.value,
                            }))
                          }
                          className="w-20 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-right text-sm text-vpv-text"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-3">
              <button
                onClick={handleSaveRules}
                disabled={savingRules || Object.keys(editedRules).length === 0}
                className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
              >
                {savingRules ? "Guardando..." : "Guardar reglas"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
