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
  scraping_slug: string | null;
  edit_unlocked: boolean;
}

interface ScoringRule {
  id: number;
  rule_key: string;
  position: string | null;
  value: number;
  description: string | null;
}

interface SeasonPayment {
  id: number;
  payment_type: string;
  position_rank: number | null;
  amount: number;
  description: string | null;
}

interface SeasonSummary {
  id: number;
  name: string;
  status: string;
  matchday_current: number;
  total_participants: number;
}

interface InitializeResponse {
  season: Season;
  participants_created: number;
  scoring_rules_copied: number;
  payments_copied: number;
  matchdays_created: number;
  scraping_started: boolean;
}

interface PhotoDownloadResponse {
  downloaded: number;
  skipped: number;
  errors: number;
  restored: number;
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
  const [payments, setPayments] = useState<SeasonPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingRules, setSavingRules] = useState(false);
  const [savingPayments, setSavingPayments] = useState(false);
  const [editedRules, setEditedRules] = useState<Record<number, string>>({});
  const [editedPayments, setEditedPayments] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  // Editable season fields
  const [editStatus, setEditStatus] = useState("");
  const [editMatchdayCurrent, setEditMatchdayCurrent] = useState("");
  const [editMatchdayEnd, setEditMatchdayEnd] = useState("");
  const [editMatchdayWinter, setEditMatchdayWinter] = useState("");
  const [editMatchdayStart, setEditMatchdayStart] = useState("");
  const [editLineupDeadline, setEditLineupDeadline] = useState("");
  const [editDraftPool, setEditDraftPool] = useState("");

  // New season modal
  const [showNewSeason, setShowNewSeason] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newCopyFrom, setNewCopyFrom] = useState<number | "">("");
  const [creatingSeason, setCreatingSeason] = useState(false);

  // Fee fields
  const [editInitialFee, setEditInitialFee] = useState("");
  const [editWinterDraft, setEditWinterDraft] = useState("");
  const [savingFees, setSavingFees] = useState(false);

  // Action states
  const [downloadingPhotos, setDownloadingPhotos] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [togglingUnlock, setTogglingUnlock] = useState(false);

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
      const [detail, scoringRules, seasonPayments] = await Promise.all([
        apiClient.get<Season>(`/seasons/${id}`),
        apiClient.get<ScoringRule[]>(`/seasons/${id}/scoring-rules`),
        apiClient.get<SeasonPayment[]>(`/seasons/${id}/payments`),
      ]);
      setSeason(detail);
      setRules(scoringRules);
      setPayments(seasonPayments);
      setEditedRules({});
      setEditedPayments({});
      // Populate fee fields from payments
      const fee = seasonPayments.find((p) => p.payment_type === "initial_fee");
      const winter = seasonPayments.find(
        (p) => p.payment_type === "winter_draft_change",
      );
      setEditInitialFee(fee ? String(fee.amount) : "");
      setEditWinterDraft(winter ? String(winter.amount) : "");
      // Populate edit fields
      setEditStatus(detail.status);
      setEditMatchdayStart(String(detail.matchday_start));
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
      if (editMatchdayStart !== String(season.matchday_start))
        body.matchday_start = Number(editMatchdayStart);
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

  const weeklyPayments = payments.filter(
    (p) => p.payment_type === "weekly_position",
  );

  const initialFee = payments.find((p) => p.payment_type === "initial_fee");
  const winterDraftChange = payments.find(
    (p) => p.payment_type === "winter_draft_change",
  );


  async function handleSavePayments() {
    if (!selectedId) return;
    const changed = Object.entries(editedPayments)
      .filter(([id, val]) => {
        const payment = payments.find((p) => p.id === Number(id));
        return payment && String(payment.amount) !== val;
      })
      .map(([id, val]) => ({ id: Number(id), amount: Number(val) }));

    if (changed.length === 0) {
      setMessage("Sin cambios en pagos");
      return;
    }

    setSavingPayments(true);
    setMessage(null);
    try {
      const updated = await apiClient.put<SeasonPayment[]>(
        `/seasons/admin/${selectedId}/payments`,
        { payments: changed },
      );
      setPayments(updated);
      setEditedPayments({});
      setMessage(`${changed.length} pago(s) actualizado(s)`);
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage("Error al guardar pagos");
    } finally {
      setSavingPayments(false);
    }
  }

  async function handleSaveFees() {
    if (!selectedId) return;
    setSavingFees(true);
    setMessage(null);
    let saved = 0;
    try {
      const feeVal = editInitialFee.trim();
      const winterVal = editWinterDraft.trim();

      if (feeVal && (!initialFee || String(initialFee.amount) !== feeVal)) {
        await apiClient.post<SeasonPayment>(
          `/seasons/admin/${selectedId}/payments`,
          {
            payment_type: "initial_fee",
            amount: Number(feeVal),
            description: "Cuota inicial",
          },
        );
        saved++;
      }

      if (
        winterVal &&
        (!winterDraftChange || String(winterDraftChange.amount) !== winterVal)
      ) {
        await apiClient.post<SeasonPayment>(
          `/seasons/admin/${selectedId}/payments`,
          {
            payment_type: "winter_draft_change",
            amount: Number(winterVal),
            description: "Coste por cambio en draft de invierno",
          },
        );
        saved++;
      }

      if (saved === 0) {
        setMessage("Sin cambios en cuotas");
      } else {
        // Refresh payments list
        const updated = await apiClient.get<SeasonPayment[]>(
          `/seasons/${selectedId}/payments`,
        );
        setPayments(updated);
        setMessage(`${saved} cuota(s) actualizada(s)`);
      }
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage("Error al guardar cuotas");
    } finally {
      setSavingFees(false);
    }
  }

  // --- New season lifecycle handlers ---

  async function handleCreateSeason() {
    if (!newName.trim() || !newSlug.trim()) {
      setMessage("Nombre y slug son obligatorios");
      return;
    }
    setCreatingSeason(true);
    setMessage(null);
    try {
      const body: Record<string, unknown> = {
        name: newName.trim(),
        scraping_slug: newSlug.trim(),
      };
      if (newCopyFrom) {
        body.copy_from_season_id = Number(newCopyFrom);
      }
      const result = await apiClient.post<InitializeResponse>(
        "/seasons/admin/initialize",
        body,
      );
      setShowNewSeason(false);
      setNewName("");
      setNewSlug("");
      setNewCopyFrom("");
      // Refresh list and select new season
      await fetchSeasons();
      setSelectedId(result.season.id);
      setMessage(
        `Temporada creada: ${result.scoring_rules_copied} reglas, ${result.payments_copied} pagos, ${result.participants_created} participantes, ${result.matchdays_created} jornadas. Importando equipos en segundo plano...`,
      );
      setTimeout(() => setMessage(null), 8000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al crear temporada";
      setMessage(msg);
    } finally {
      setCreatingSeason(false);
    }
  }

  async function handleDownloadPhotos() {
    if (!selectedId) return;
    if (!confirm("Descargar fotos de jugadores? El proceso puede tardar varios minutos.")) return;
    setDownloadingPhotos(true);
    setMessage("Descargando fotos...");
    try {
      const result = await apiClient.post<PhotoDownloadResponse>(
        `/seasons/admin/${selectedId}/download-photos`,
        {},
      );
      setMessage(
        `Fotos: ${result.downloaded} descargadas, ${result.restored} restauradas, ${result.skipped} omitidas, ${result.errors} errores`,
      );
      setTimeout(() => setMessage(null), 8000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al descargar fotos";
      setMessage(msg);
    } finally {
      setDownloadingPhotos(false);
    }
  }

  async function handleToggleEditUnlock() {
    if (!selectedId || !season) return;
    const next = !season.edit_unlocked;
    if (next) {
      if (
        !confirm(
          `DESBLOQUEAR edicion de la temporada FINALIZADA ${season.name}?\n\n` +
            "Los cambios afectaran datos historicos. Usa solo si es estrictamente necesario.",
        )
      )
        return;
    }
    setTogglingUnlock(true);
    setMessage(null);
    try {
      const updated = await apiClient.put<Season>(
        `/seasons/admin/${selectedId}/edit-unlock`,
        { unlocked: next },
      );
      setSeason(updated);
      setMessage(next ? "Edicion DESBLOQUEADA" : "Edicion bloqueada");
      setTimeout(() => setMessage(null), 4000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al cambiar estado";
      setMessage(msg);
    } finally {
      setTogglingUnlock(false);
    }
  }

  async function handleFinalizeSeason() {
    if (!selectedId || !season) return;
    if (!confirm(`Finalizar la temporada ${season.name}? Esta accion no se puede deshacer facilmente.`)) return;
    setFinalizing(true);
    setMessage(null);
    try {
      const result = await apiClient.put<{ season: Season }>(
        `/seasons/admin/${selectedId}/finalize`,
        {},
      );
      setSeason(result.season);
      setEditStatus(result.season.status);
      await fetchSeasons();
      setMessage("Temporada finalizada");
      setTimeout(() => setMessage(null), 5000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al finalizar";
      setMessage(msg);
    } finally {
      setFinalizing(false);
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
      {/* Season selector + New season button */}
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
        <button
          onClick={() => setShowNewSeason(true)}
          className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-700"
        >
          + Nueva temporada
        </button>
      </div>

      {/* New season modal */}
      {showNewSeason && (
        <div className="rounded-lg border border-green-600/30 bg-vpv-card">
          <div className="border-b border-vpv-border px-4 py-3">
            <h2 className="font-semibold text-vpv-text">Crear nueva temporada</h2>
          </div>
          <div className="space-y-3 px-4 py-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs text-vpv-text-muted">
                  Nombre *
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="2026-2027"
                  className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-vpv-text-muted">
                  Slug scraping *
                </label>
                <input
                  type="text"
                  value={newSlug}
                  onChange={(e) => setNewSlug(e.target.value)}
                  placeholder="laliga-26-27"
                  className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-vpv-text-muted">
                  Copiar config de
                </label>
                <select
                  value={newCopyFrom}
                  onChange={(e) => setNewCopyFrom(e.target.value ? Number(e.target.value) : "")}
                  className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                >
                  <option value="">— No copiar —</option>
                  {seasons.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="text-xs text-vpv-text-muted">
              Se crearan 38 jornadas vacias. Si copias de otra temporada se copian reglas, pagos y participantes.
              Los equipos y jugadores se importan automaticamente en segundo plano (~2-3 min).
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCreateSeason}
                disabled={creatingSeason}
                className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
              >
                {creatingSeason ? "Creando..." : "Crear temporada"}
              </button>
              <button
                onClick={() => setShowNewSeason(false)}
                className="rounded border border-vpv-border px-3 py-1.5 text-xs text-vpv-text-muted transition-colors hover:bg-vpv-bg"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Status message */}
      {message && (
        <div className="rounded border border-vpv-border bg-vpv-bg px-4 py-2 text-sm text-vpv-text">
          {message}
        </div>
      )}

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
                    Jornada inicial
                  </label>
                  <input
                    type="number"
                    value={editMatchdayStart}
                    onChange={(e) => setEditMatchdayStart(e.target.value)}
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
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
                <span>Scanned: J{season.matchday_scanned}</span>
                <span>Participantes: {season.total_participants}</span>
                {season.scraping_slug && <span>Slug: {season.scraping_slug}</span>}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={handleSaveSeason}
                  disabled={saving}
                  className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
                >
                  {saving ? "Guardando..." : "Guardar cambios"}
                </button>
                <button
                  onClick={handleDownloadPhotos}
                  disabled={downloadingPhotos}
                  className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                >
                  {downloadingPhotos ? "Descargando fotos..." : "Descargar fotos"}
                </button>
                {season.status === "active" && (
                  <button
                    onClick={handleFinalizeSeason}
                    disabled={finalizing}
                    className="rounded bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                  >
                    {finalizing ? "Finalizando..." : "Finalizar temporada"}
                  </button>
                )}
                {season.status === "finished" && (
                  <button
                    onClick={handleToggleEditUnlock}
                    disabled={togglingUnlock}
                    className={`rounded px-3 py-1.5 text-xs font-medium text-white transition-colors disabled:opacity-50 ${
                      season.edit_unlocked
                        ? "bg-amber-600 hover:bg-amber-700"
                        : "bg-zinc-700 hover:bg-zinc-600"
                    }`}
                  >
                    {togglingUnlock
                      ? "Cambiando..."
                      : season.edit_unlocked
                        ? "Bloquear edicion"
                        : "Desbloquear edicion"}
                  </button>
                )}
              </div>

              {season.status === "finished" && season.edit_unlocked && (
                <div className="rounded border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                  <strong>WARNING:</strong> Temporada DESBLOQUEADA para edicion.
                  Los cambios afectaran datos historicos. Bloquea de nuevo
                  cuando termines.
                </div>
              )}
              {season.status === "finished" && !season.edit_unlocked && (
                <div className="rounded border border-vpv-border bg-vpv-bg px-3 py-2 text-xs text-vpv-text-muted">
                  Temporada finalizada y bloqueada. Las modificaciones estan
                  deshabilitadas. Usa el boton para desbloquear si necesitas
                  corregir algo historico.
                </div>
              )}
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

          {/* Cuota inicial + Coste draft invierno */}
          <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
            <div className="border-b border-vpv-border px-4 py-3">
              <h2 className="font-semibold text-vpv-text">Cuotas y costes</h2>
            </div>
            <div className="space-y-3 px-4 py-3">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Cuota inicial
                  </label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      step="0.01"
                      value={editInitialFee}
                      onChange={(e) => setEditInitialFee(e.target.value)}
                      placeholder="0.00"
                      className="w-24 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                    />
                    <span className="text-xs text-vpv-text-muted">EUR</span>
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Coste cambio draft invierno
                  </label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      step="0.01"
                      value={editWinterDraft}
                      onChange={(e) => setEditWinterDraft(e.target.value)}
                      placeholder="0.00"
                      className="w-24 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                    />
                    <span className="text-xs text-vpv-text-muted">EUR</span>
                  </div>
                </div>
              </div>
              <button
                onClick={handleSaveFees}
                disabled={savingFees}
                className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
              >
                {savingFees ? "Guardando..." : "Guardar cuotas"}
              </button>
            </div>
          </div>

          {/* Weekly position payments */}
          {weeklyPayments.length > 0 && (
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
              <div className="border-b border-vpv-border px-4 py-3">
                <h2 className="font-semibold text-vpv-text">
                  Pagos semanales por posicion
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
                      <th className="px-4 py-2">Posicion</th>
                      <th className="px-4 py-2">Descripcion</th>
                      <th className="px-4 py-2 text-right">Importe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {weeklyPayments
                      .sort(
                        (a, b) =>
                          (a.position_rank ?? 0) - (b.position_rank ?? 0),
                      )
                      .map((p) => (
                        <tr
                          key={p.id}
                          className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                        >
                          <td className="px-4 py-2 font-medium text-vpv-text">
                            {p.position_rank !== null
                              ? `${p.position_rank}°`
                              : "—"}
                          </td>
                          <td className="px-4 py-2 text-vpv-text-muted">
                            {p.description ?? "—"}
                          </td>
                          <td className="px-4 py-2 text-right">
                            <input
                              type="number"
                              step="0.01"
                              value={
                                editedPayments[p.id] !== undefined
                                  ? editedPayments[p.id]
                                  : String(p.amount)
                              }
                              onChange={(e) =>
                                setEditedPayments((prev) => ({
                                  ...prev,
                                  [p.id]: e.target.value,
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
                  onClick={handleSavePayments}
                  disabled={
                    savingPayments ||
                    Object.keys(editedPayments).length === 0
                  }
                  className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
                >
                  {savingPayments ? "Guardando..." : "Guardar pagos"}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
