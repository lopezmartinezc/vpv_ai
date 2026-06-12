"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { PlayoffsCard } from "@/components/admin/playoffs-card";

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
  kind?: "league" | "tournament";
  weekly_payments_enabled?: boolean;
  tournament_type?: string | null;
  telegram_chat_id?: string | null;
  alerts_telegram_chat_id?: string | null;
  alerts_telegram_thread_id?: number | null;
  alerts_config?: { events?: Record<string, boolean> } | null;
  telegram_thread_id?: number | null;
  draft_telegram_chat_id?: string | null;
  draft_telegram_thread_id?: number | null;
  tournament_config?: Record<string, unknown> | null;
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
  // Key is "id:N" for existing rows or "new:R" (R = position_rank) for rows
  // that don't yet exist in season_payments — the save handler dispatches
  // PUT for updates and POST for new rows.
  const [editedPayments, setEditedPayments] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  // Editable season fields
  const [editStatus, setEditStatus] = useState("");
  const [editName, setEditName] = useState("");
  const [editWeeklyPaymentsEnabled, setEditWeeklyPaymentsEnabled] =
    useState(false);
  const [editSlug, setEditSlug] = useState("");
  const [editTelegramChatId, setEditTelegramChatId] = useState("");
  const [editTelegramThreadId, setEditTelegramThreadId] = useState("");
  const [editDraftTelegramChatId, setEditDraftTelegramChatId] = useState("");
  const [editDraftTelegramThreadId, setEditDraftTelegramThreadId] = useState("");
  const [editAlertsTelegramChatId, setEditAlertsTelegramChatId] = useState("");
  const [editAlertsTelegramThreadId, setEditAlertsTelegramThreadId] = useState("");
  // Alert-event toggles. Defaults to true: matches the backend
  // `is_alert_event_enabled` fallback, so the UI shows the same
  // truth as `send_alert` will apply at runtime.
  const [editAlertDeadlineReminder, setEditAlertDeadlineReminder] = useState(true);
  const [editAlertLineupSubmitted, setEditAlertLineupSubmitted] = useState(true);
  const [editAlertLiveMatchEvents, setEditAlertLiveMatchEvents] = useState(true);
  const [editMatchdayCurrent, setEditMatchdayCurrent] = useState("");
  const [editMatchdayEnd, setEditMatchdayEnd] = useState("");
  const [editMatchdayWinter, setEditMatchdayWinter] = useState("");
  const [editMatchdayStart, setEditMatchdayStart] = useState("");
  const [editLineupDeadline, setEditLineupDeadline] = useState("");
  const [editDraftPool, setEditDraftPool] = useState("");
  const [editTournamentConfig, setEditTournamentConfig] = useState("");
  const [tournamentConfigError, setTournamentConfigError] = useState<string | null>(null);

  // New season modal
  const [showNewSeason, setShowNewSeason] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newCopyFrom, setNewCopyFrom] = useState<number | "">("");
  const [newKind, setNewKind] = useState<"league" | "tournament">("league");
  const [newTournamentType, setNewTournamentType] = useState("mundial");
  const [newMatchdayEnd, setNewMatchdayEnd] = useState("38");
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
      setEditName(detail.name);
      setEditWeeklyPaymentsEnabled(
        detail.weekly_payments_enabled ?? detail.kind !== "tournament",
      );
      setEditSlug(detail.scraping_slug ?? "");
      setEditTelegramChatId(detail.telegram_chat_id ?? "");
      setEditTelegramThreadId(
        detail.telegram_thread_id != null ? String(detail.telegram_thread_id) : "",
      );
      setEditDraftTelegramChatId(detail.draft_telegram_chat_id ?? "");
      setEditDraftTelegramThreadId(
        detail.draft_telegram_thread_id != null ? String(detail.draft_telegram_thread_id) : "",
      );
      setEditAlertsTelegramChatId(detail.alerts_telegram_chat_id ?? "");
      setEditAlertsTelegramThreadId(
        detail.alerts_telegram_thread_id != null ? String(detail.alerts_telegram_thread_id) : "",
      );
      const events = detail.alerts_config?.events ?? {};
      setEditAlertDeadlineReminder(events.deadline_reminder !== false);
      setEditAlertLineupSubmitted(events.lineup_submitted !== false);
      setEditAlertLiveMatchEvents(events.live_match_events !== false);
      setEditTournamentConfig(
        detail.tournament_config
          ? JSON.stringify(detail.tournament_config, null, 2)
          : "",
      );
      setTournamentConfigError(null);
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
      if (editName.trim() !== season.name) body.name = editName.trim();
      if (editSlug !== (season.scraping_slug ?? ""))
        body.scraping_slug = editSlug || null;
      const currentWeekly =
        season.weekly_payments_enabled ?? season.kind !== "tournament";
      if (editWeeklyPaymentsEnabled !== currentWeekly) {
        body.weekly_payments_enabled = editWeeklyPaymentsEnabled;
      }
      if (editTelegramChatId !== (season.telegram_chat_id ?? ""))
        body.telegram_chat_id = editTelegramChatId || null;
      const currentGeneralThreadId =
        season.telegram_thread_id != null ? String(season.telegram_thread_id) : "";
      if (editTelegramThreadId !== currentGeneralThreadId) {
        body.telegram_thread_id = editTelegramThreadId
          ? Number(editTelegramThreadId)
          : null;
      }
      if (editDraftTelegramChatId !== (season.draft_telegram_chat_id ?? ""))
        body.draft_telegram_chat_id = editDraftTelegramChatId || null;
      const currentThreadId =
        season.draft_telegram_thread_id != null
          ? String(season.draft_telegram_thread_id)
          : "";
      if (editDraftTelegramThreadId !== currentThreadId) {
        body.draft_telegram_thread_id = editDraftTelegramThreadId
          ? Number(editDraftTelegramThreadId)
          : null;
      }

      if (editAlertsTelegramChatId !== (season.alerts_telegram_chat_id ?? ""))
        body.alerts_telegram_chat_id = editAlertsTelegramChatId || null;
      const currentAlertsThreadId =
        season.alerts_telegram_thread_id != null
          ? String(season.alerts_telegram_thread_id)
          : "";
      if (editAlertsTelegramThreadId !== currentAlertsThreadId) {
        body.alerts_telegram_thread_id = editAlertsTelegramThreadId
          ? Number(editAlertsTelegramThreadId)
          : null;
      }

      // Event toggles: only ship the keys that are disabled, since the
      // backend treats absence as "enabled" and the JSONB stays small.
      const currentEvents = season.alerts_config?.events ?? {};
      const currentValue = {
        deadline_reminder: currentEvents.deadline_reminder !== false,
        lineup_submitted: currentEvents.lineup_submitted !== false,
        live_match_events: currentEvents.live_match_events !== false,
      };
      const nextValue = {
        deadline_reminder: editAlertDeadlineReminder,
        lineup_submitted: editAlertLineupSubmitted,
        live_match_events: editAlertLiveMatchEvents,
      };
      if (
        currentValue.deadline_reminder !== nextValue.deadline_reminder ||
        currentValue.lineup_submitted !== nextValue.lineup_submitted ||
        currentValue.live_match_events !== nextValue.live_match_events
      ) {
        const eventsPayload: Record<string, boolean> = {};
        if (!nextValue.deadline_reminder) eventsPayload.deadline_reminder = false;
        if (!nextValue.lineup_submitted) eventsPayload.lineup_submitted = false;
        if (!nextValue.live_match_events) eventsPayload.live_match_events = false;
        // Send `{events: {...}}` even when empty — the backend's
        // SeasonUpdate.model_dump(exclude_none=True) drops nulls, so
        // we can't clear via `null`. An empty events dict is treated
        // as "every event enabled" by is_alert_event_enabled.
        body.alerts_config = { events: eventsPayload };
      }

      // tournament_config is a JSON textarea
      const currentConfigJson = season.tournament_config
        ? JSON.stringify(season.tournament_config, null, 2)
        : "";
      if (editTournamentConfig !== currentConfigJson) {
        if (editTournamentConfig.trim() === "") {
          body.tournament_config = null;
        } else {
          try {
            body.tournament_config = JSON.parse(editTournamentConfig);
            setTournamentConfigError(null);
          } catch (e) {
            setTournamentConfigError(
              `JSON invalido: ${e instanceof Error ? e.message : String(e)}`,
            );
            setSaving(false);
            return;
          }
        }
      }
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

    const updates: { id: number; amount: number }[] = [];
    const creates: { position_rank: number; amount: number }[] = [];

    for (const [key, val] of Object.entries(editedPayments)) {
      const trimmed = val.trim();
      if (key.startsWith("id:")) {
        const id = Number(key.slice(3));
        const p = payments.find((x) => x.id === id);
        if (!p) continue;
        const newAmount = trimmed === "" ? 0 : Number(trimmed);
        if (Number.isNaN(newAmount)) continue;
        if (Number(p.amount) !== newAmount) {
          updates.push({ id, amount: newAmount });
        }
      } else if (key.startsWith("new:")) {
        const rank = Number(key.slice(4));
        if (trimmed === "") continue;
        const amount = Number(trimmed);
        if (Number.isNaN(amount) || amount === 0) continue;
        creates.push({ position_rank: rank, amount });
      }
    }

    if (updates.length === 0 && creates.length === 0) {
      setMessage("Sin cambios en pagos");
      return;
    }

    setSavingPayments(true);
    setMessage(null);
    try {
      if (updates.length > 0) {
        await apiClient.put<SeasonPayment[]>(
          `/seasons/admin/${selectedId}/payments`,
          { payments: updates },
        );
      }
      for (const c of creates) {
        await apiClient.post<SeasonPayment>(
          `/seasons/admin/${selectedId}/payments`,
          {
            payment_type: "weekly_position",
            position_rank: c.position_rank,
            amount: c.amount,
            description: `Posición ${c.position_rank}`,
          },
        );
      }
      const reloaded = await apiClient.get<SeasonPayment[]>(
        `/seasons/${selectedId}/payments`,
      );
      setPayments(reloaded);
      setEditedPayments({});
      const total = updates.length + creates.length;
      setMessage(`${total} pago(s) guardado(s)`);
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
        kind: newKind,
        matchday_end: Number(newMatchdayEnd),
      };
      if (newCopyFrom) {
        body.copy_from_season_id = Number(newCopyFrom);
      }
      if (newKind === "tournament") {
        body.tournament_type = newTournamentType;
        if (newTournamentType === "mundial") {
          // Mundial 2026 (FIFA Regulations Article 12): 48 teams, 12 groups
          // of 4. Knockout: R32 -> R16 -> QF -> SF -> 3rd + Final.
          // Pairing codes:
          //   "1A"  = winner of Group A
          //   "2A"  = runner-up of Group A
          //   "3:ABCDF" = Best 3rd from combination ABCDF (resolved via Annexe C)
          //   "W74" = winner of match M74
          //   "L101" = loser of match M101
          body.tournament_config = {
            groups: { count: 12, teams_per_group: 4, matchdays: [1, 2, 3] },
            knockout: {
              rounds: [
                {
                  name: "16avos",
                  matchday: 4,
                  matches: 16,
                  pairings: [
                    { code: "M73", home: "2A", away: "2B" },
                    { code: "M74", home: "1E", away: "3:ABCDF" },
                    { code: "M75", home: "1F", away: "2C" },
                    { code: "M76", home: "1C", away: "2F" },
                    { code: "M77", home: "1I", away: "3:CDFGH" },
                    { code: "M78", home: "2E", away: "2I" },
                    { code: "M79", home: "1A", away: "3:CEFHI" },
                    { code: "M80", home: "1L", away: "3:EHIJK" },
                    { code: "M81", home: "1D", away: "3:BEFIJ" },
                    { code: "M82", home: "1G", away: "3:AEHIJ" },
                    { code: "M83", home: "2K", away: "2L" },
                    { code: "M84", home: "1H", away: "2J" },
                    { code: "M85", home: "1B", away: "3:EFGIJ" },
                    { code: "M86", home: "1J", away: "2H" },
                    { code: "M87", home: "1K", away: "3:DEIJL" },
                    { code: "M88", home: "2D", away: "2G" },
                  ],
                },
                {
                  name: "octavos",
                  matchday: 5,
                  matches: 8,
                  pairings: [
                    { code: "M89", home: "W74", away: "W77" },
                    { code: "M90", home: "W73", away: "W75" },
                    { code: "M91", home: "W76", away: "W78" },
                    { code: "M92", home: "W79", away: "W80" },
                    { code: "M93", home: "W83", away: "W84" },
                    { code: "M94", home: "W81", away: "W82" },
                    { code: "M95", home: "W86", away: "W88" },
                    { code: "M96", home: "W85", away: "W87" },
                  ],
                },
                {
                  name: "cuartos",
                  matchday: 6,
                  matches: 4,
                  pairings: [
                    { code: "M97", home: "W89", away: "W90" },
                    { code: "M98", home: "W93", away: "W94" },
                    { code: "M99", home: "W91", away: "W92" },
                    { code: "M100", home: "W95", away: "W96" },
                  ],
                },
                {
                  name: "semis",
                  matchday: 7,
                  matches: 2,
                  pairings: [
                    { code: "M101", home: "W97", away: "W98" },
                    { code: "M102", home: "W99", away: "W100" },
                  ],
                },
                {
                  name: "final",
                  matchday: 8,
                  matches: 2,
                  pairings: [
                    { code: "M103", home: "L101", away: "L102", label: "3er puesto" },
                    { code: "M104", home: "W101", away: "W102", label: "Final" },
                  ],
                },
              ],
            },
            third_place_match: true,
            predictions_enabled: true,
          };
        } else if (newTournamentType === "eurocopa") {
          body.tournament_config = {
            groups: { count: 6, teams_per_group: 4, matchdays: [1, 2, 3] },
            knockout: {
              rounds: [
                { name: "octavos", matchday: 4, matches: 8 },
                { name: "cuartos", matchday: 5, matches: 4 },
                { name: "semis", matchday: 6, matches: 2 },
                { name: "final", matchday: 7, matches: 1 },
              ],
            },
            best_third_place_count: 4,
            predictions_enabled: true,
          };
        }
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
            {/* Tipo */}
            <div>
              <label className="mb-1 block text-xs text-vpv-text-muted">
                Tipo de competicion
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setNewKind("league");
                    setNewMatchdayEnd("38");
                  }}
                  className={`flex-1 rounded border px-3 py-1.5 text-xs font-medium transition-colors ${
                    newKind === "league"
                      ? "border-vpv-accent bg-vpv-accent/10 text-vpv-accent"
                      : "border-vpv-border text-vpv-text-muted hover:bg-vpv-bg"
                  }`}
                >
                  ⚽ Liga (38 jornadas)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setNewKind("tournament");
                    setNewMatchdayEnd("8");
                  }}
                  className={`flex-1 rounded border px-3 py-1.5 text-xs font-medium transition-colors ${
                    newKind === "tournament"
                      ? "border-vpv-accent bg-vpv-accent/10 text-vpv-accent"
                      : "border-vpv-border text-vpv-text-muted hover:bg-vpv-bg"
                  }`}
                >
                  🏆 Torneo
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs text-vpv-text-muted">
                  Nombre *
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={newKind === "league" ? "2026-2027" : "Mundial 26"}
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
                  placeholder={newKind === "league" ? "laliga-26-27" : "mundial-2026"}
                  className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                />
              </div>
              {newKind === "tournament" && (
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Tipo de torneo
                  </label>
                  <select
                    value={newTournamentType}
                    onChange={(e) => setNewTournamentType(e.target.value)}
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  >
                    <option value="mundial">Mundial</option>
                    <option value="eurocopa">Eurocopa</option>
                    <option value="copa_america">Copa America</option>
                  </select>
                </div>
              )}
              <div>
                <label className="mb-1 block text-xs text-vpv-text-muted">
                  Jornadas (total)
                </label>
                <input
                  type="number"
                  value={newMatchdayEnd}
                  onChange={(e) => setNewMatchdayEnd(e.target.value)}
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
              {newKind === "league"
                ? `Se crearan ${newMatchdayEnd} jornadas vacias. Si copias de otra temporada se copian reglas, pagos y participantes. Los equipos y jugadores se importan automaticamente en segundo plano (~2-3 min).`
                : `Se crearan ${newMatchdayEnd} jornadas (grupos + eliminatorias). El tournament_config se configura automaticamente. Si copias de otra temporada se copian reglas, pagos y participantes.`}
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
                    Nombre (max 15)
                  </label>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    maxLength={15}
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Slug scraping
                  </label>
                  <input
                    type="text"
                    value={editSlug}
                    onChange={(e) => setEditSlug(e.target.value)}
                    placeholder="world-cup, laliga-25-26, ..."
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Telegram chat ID
                  </label>
                  <input
                    type="text"
                    value={editTelegramChatId}
                    onChange={(e) => setEditTelegramChatId(e.target.value)}
                    placeholder="(usa el global)"
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Telegram thread ID (alineaciones)
                  </label>
                  <input
                    type="number"
                    inputMode="numeric"
                    value={editTelegramThreadId}
                    onChange={(e) => setEditTelegramThreadId(e.target.value)}
                    placeholder="Topic ID (sólo grupos con topics)"
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Telegram chat ID del Draft
                  </label>
                  <input
                    type="text"
                    value={editDraftTelegramChatId}
                    onChange={(e) => setEditDraftTelegramChatId(e.target.value)}
                    placeholder="Canal específico del draft (opcional)"
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Telegram thread ID del Draft
                  </label>
                  <input
                    type="number"
                    inputMode="numeric"
                    value={editDraftTelegramThreadId}
                    onChange={(e) => setEditDraftTelegramThreadId(e.target.value)}
                    placeholder="Topic ID (sólo grupos con topics)"
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Telegram chat ID de Alertas
                  </label>
                  <input
                    type="text"
                    value={editAlertsTelegramChatId}
                    onChange={(e) => setEditAlertsTelegramChatId(e.target.value)}
                    placeholder="Canal específico para deadline reminders y warnings"
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                  <p className="mt-1 text-xs text-vpv-text-muted">
                    Si lo dejas vacío, las alertas van al chat general de la temporada (con su thread).
                  </p>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-vpv-text-muted">
                    Telegram thread ID de Alertas
                  </label>
                  <input
                    type="number"
                    inputMode="numeric"
                    value={editAlertsTelegramThreadId}
                    onChange={(e) => setEditAlertsTelegramThreadId(e.target.value)}
                    placeholder="Topic ID (sólo grupos con topics)"
                    className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
                  />
                </div>

                <div className="rounded border border-vpv-border bg-vpv-bg/40 p-3">
                  <p className="mb-2 text-xs font-medium text-vpv-text">
                    Eventos que disparan alertas Telegram
                  </p>
                  <div className="space-y-1.5">
                    <label className="flex cursor-pointer items-center gap-2 text-xs text-vpv-text">
                      <input
                        type="checkbox"
                        checked={editAlertDeadlineReminder}
                        onChange={(e) => setEditAlertDeadlineReminder(e.target.checked)}
                      />
                      <span>
                        <strong>Recordatorios de deadline</strong> — &quot;Faltan
                        Xh para el deadline&quot; con lista de participantes sin
                        alineación.
                      </span>
                    </label>
                    <label className="flex cursor-pointer items-center gap-2 text-xs text-vpv-text">
                      <input
                        type="checkbox"
                        checked={editAlertLineupSubmitted}
                        onChange={(e) => setEditAlertLineupSubmitted(e.target.checked)}
                      />
                      <span>
                        <strong>Alineación enviada</strong> — imagen + caption
                        cuando un participante guarda su alineación.
                      </span>
                    </label>
                    <label className="flex cursor-pointer items-center gap-2 text-xs text-vpv-text">
                      <input
                        type="checkbox"
                        checked={editAlertLiveMatchEvents}
                        onChange={(e) => setEditAlertLiveMatchEvents(e.target.checked)}
                      />
                      <span>
                        <strong>Eventos en vivo</strong> — goles, tarjetas y
                        cambios mientras se juega el partido.
                      </span>
                    </label>
                  </div>
                  <p className="mt-2 text-xs text-vpv-text-muted">
                    Por defecto todos los eventos están activos. Desactiva los
                    que quieras silenciar para esta temporada.
                  </p>
                </div>
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
                    Pagos semanales por posicion
                  </label>
                  <label className="flex items-center gap-2 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text">
                    <input
                      type="checkbox"
                      checked={editWeeklyPaymentsEnabled}
                      onChange={(e) =>
                        setEditWeeklyPaymentsEnabled(e.target.checked)
                      }
                    />
                    <span>
                      {editWeeklyPaymentsEnabled
                        ? "Activados"
                        : "Desactivados"}
                    </span>
                  </label>
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
                {season.kind !== "tournament" && (
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
                )}
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
                {season.kind === "tournament" && season.tournament_type && (
                  <span>Tipo: {season.tournament_type}</span>
                )}
              </div>

              {season.kind === "tournament" && (
                <div className="space-y-3">
                  <div>
                    <label className="mb-1 block text-xs text-vpv-text-muted">
                      Fuente del scrape de stats
                    </label>
                    <select
                      value={(() => {
                        try {
                          const parsed = editTournamentConfig
                            ? JSON.parse(editTournamentConfig)
                            : {};
                          const v = parsed?.stats_source;
                          return v === "match_page" ? "match_page" : "player_page";
                        } catch {
                          return "player_page";
                        }
                      })()}
                      onChange={(e) => {
                        let parsed: Record<string, unknown> = {};
                        try {
                          parsed = editTournamentConfig
                            ? JSON.parse(editTournamentConfig)
                            : {};
                        } catch {
                          // ignore — overwrite the broken JSON with a fresh object.
                        }
                        if (e.target.value === "match_page") {
                          parsed.stats_source = "match_page";
                        } else {
                          delete parsed.stats_source;
                        }
                        const next = Object.keys(parsed).length
                          ? JSON.stringify(parsed, null, 2)
                          : "";
                        setEditTournamentConfig(next);
                        setTournamentConfigError(null);
                      }}
                      className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-xs text-vpv-text"
                    >
                      <option value="player_page">
                        Pagina del jugador (defecto — Liga)
                      </option>
                      <option value="match_page">
                        Pagina del partido (Mundial / torneos)
                      </option>
                    </select>
                    <p className="mt-1 text-xs text-vpv-text-muted">
                      Las paginas individuales de jugadores del Mundial no
                      tienen tabla por jornada. Selecciona &quot;pagina del partido&quot;
                      para scrapear los 52 jugadores de cada partido en un solo fetch.
                      Cambia <code>tournament_config.stats_source</code> en el JSON.
                    </p>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs text-vpv-text-muted">
                      Configuracion del torneo (JSON)
                    </label>
                    <textarea
                      value={editTournamentConfig}
                      onChange={(e) => {
                        setEditTournamentConfig(e.target.value);
                        setTournamentConfigError(null);
                      }}
                      rows={12}
                      spellCheck={false}
                      placeholder='{"groups": {"count": 12, ...}, "knockout": {...}}'
                      className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 font-mono text-xs text-vpv-text"
                    />
                    {tournamentConfigError && (
                      <p className="mt-1 text-xs text-red-400">{tournamentConfigError}</p>
                    )}
                    <p className="mt-1 text-xs text-vpv-text-muted">
                      Estructura: groups.count, groups.teams_per_group, groups.matchdays[], knockout.rounds[]
                    </p>
                  </div>
                </div>
              )}

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

          {/* Playoffs — torneo = 1 playoff. Liga = Apertura + Clausura */}
          {season.kind === "tournament" && (
            <PlayoffsCard
              seasonId={season.id}
              matchdayStart={season.matchday_start}
              matchdayEnd={season.matchday_end}
              defaultFormatId="balanced_ko4"
            />
          )}
          {season.kind === "league" && (
            <div className="space-y-3">
              <PlayoffsCard
                seasonId={season.id}
                matchdayStart={season.matchday_start}
                matchdayEnd={season.matchday_end}
                playoffName="Apertura"
                title="Playoff Apertura"
                defaultFormatId="liga_berger_ko8"
              />
              <PlayoffsCard
                seasonId={season.id}
                matchdayStart={season.matchday_start}
                matchdayEnd={season.matchday_end}
                playoffName="Clausura"
                title="Playoff Clausura"
                defaultFormatId="liga_berger_ko8"
              />
            </div>
          )}

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
                {season.kind !== "tournament" && (
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
                )}
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

          {/* Weekly position payments — controlado por season.weekly_payments_enabled */}
          {season && !season.weekly_payments_enabled && (
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
              <div className="border-b border-vpv-border px-4 py-3">
                <h2 className="font-semibold text-vpv-text">
                  Pagos semanales por posicion
                </h2>
                <p className="mt-1 text-xs text-vpv-text-muted">
                  Desactivados para esta temporada. Activa el toggle de arriba
                  para configurar pagos por puesto en cada jornada.
                </p>
              </div>
            </div>
          )}
          {season && season.weekly_payments_enabled && season.total_participants > 0 && (
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
              <div className="border-b border-vpv-border px-4 py-3">
                <h2 className="font-semibold text-vpv-text">
                  Pagos semanales por posicion
                </h2>
                <p className="mt-1 text-xs text-vpv-text-muted">
                  {season.total_participants} participantes. Deja en blanco las
                  posiciones que no cobran.
                </p>
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
                    {(() => {
                      const byRank = new Map(
                        weeklyPayments
                          .filter((p) => p.position_rank !== null)
                          .map((p) => [p.position_rank as number, p]),
                      );
                      return Array.from(
                        { length: season.total_participants },
                        (_, i) => i + 1,
                      ).map((rank) => {
                        const existing = byRank.get(rank) ?? null;
                        const key = existing
                          ? `id:${existing.id}`
                          : `new:${rank}`;
                        const value =
                          editedPayments[key] !== undefined
                            ? editedPayments[key]
                            : existing
                              ? String(existing.amount)
                              : "";
                        return (
                          <tr
                            key={key}
                            className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                          >
                            <td className="px-4 py-2 font-medium text-vpv-text">
                              {rank}°
                            </td>
                            <td className="px-4 py-2 text-vpv-text-muted">
                              {existing?.description ?? "—"}
                            </td>
                            <td className="px-4 py-2 text-right">
                              <input
                                type="number"
                                step="0.01"
                                value={value}
                                placeholder="0"
                                onChange={(e) =>
                                  setEditedPayments((prev) => ({
                                    ...prev,
                                    [key]: e.target.value,
                                  }))
                                }
                                className="w-20 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-right text-sm text-vpv-text"
                              />
                            </td>
                          </tr>
                        );
                      });
                    })()}
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
