"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { apiClient } from "@/lib/api-client";
import { SeasonSelector } from "@/components/layout/season-selector";
import type {
  CreateDraftResponse,
  DraftDetailResponse,
  DraftListResponse,
  DraftParticipant,
  DraftPickEntry,
} from "@/types";

const PHASE_LABELS: Record<string, string> = {
  preseason: "Pretemporada",
  winter: "Invierno",
};
const TYPE_LABELS: Record<string, string> = {
  snake: "Serpiente",
  linear: "Lineal",
};
const POS_COLORS: Record<string, string> = {
  POR: "bg-amber-600/20 text-amber-400",
  DEF: "bg-blue-600/20 text-blue-400",
  MED: "bg-green-600/20 text-green-400",
  DEL: "bg-red-600/20 text-red-400",
};

const PARTICIPANT_COLORS = [
  { border: "border-l-blue-500", bg: "bg-blue-500/10", chip: "bg-blue-500", text: "text-blue-400" },
  { border: "border-l-emerald-500", bg: "bg-emerald-500/10", chip: "bg-emerald-500", text: "text-emerald-400" },
  { border: "border-l-amber-500", bg: "bg-amber-500/10", chip: "bg-amber-500", text: "text-amber-400" },
  { border: "border-l-red-500", bg: "bg-red-500/10", chip: "bg-red-500", text: "text-red-400" },
  { border: "border-l-purple-500", bg: "bg-purple-500/10", chip: "bg-purple-500", text: "text-purple-400" },
  { border: "border-l-cyan-500", bg: "bg-cyan-500/10", chip: "bg-cyan-500", text: "text-cyan-400" },
  { border: "border-l-pink-500", bg: "bg-pink-500/10", chip: "bg-pink-500", text: "text-pink-400" },
  { border: "border-l-orange-500", bg: "bg-orange-500/10", chip: "bg-orange-500", text: "text-orange-400" },
  { border: "border-l-lime-500", bg: "bg-lime-500/10", chip: "bg-lime-500", text: "text-lime-400" },
  { border: "border-l-indigo-500", bg: "bg-indigo-500/10", chip: "bg-indigo-500", text: "text-indigo-400" },
  { border: "border-l-teal-500", bg: "bg-teal-500/10", chip: "bg-teal-500", text: "text-teal-400" },
];


function getColorForParticipant(
  participantId: number,
  participants: DraftParticipant[],
): (typeof PARTICIPANT_COLORS)[number] {
  const idx = participants.findIndex((p) => p.participant_id === participantId);
  return PARTICIPANT_COLORS[(idx >= 0 ? idx : 0) % PARTICIPANT_COLORS.length];
}

export default function GestionarDraftPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason, loading: seasonLoading } = useSeason();

  const [drafts, setDrafts] = useState<DraftListResponse | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<string>("preseason");
  const [draftDetail, setDraftDetail] = useState<DraftDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Participants from draft detail (not loaded separately)
  const participants = draftDetail?.participants ?? [];
  const orderedParticipants = [...participants].sort(
    (a, b) => (a.draft_order ?? 999) - (b.draft_order ?? 999),
  );

  // Pick reorder state
  const [filterParticipantId, setFilterParticipantId] = useState<number | null>(null);
  const [localPicks, setLocalPicks] = useState<DraftPickEntry[]>([]);
  const [hasReorderChanges, setHasReorderChanges] = useState(false);
  const [savingReorder, setSavingReorder] = useState(false);

  // Drag state
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const dragNodeRef = useRef<HTMLDivElement | null>(null);

  // Participant order (editable copy)
  const [editableParticipants, setEditableParticipants] = useState<DraftParticipant[]>([]);

  // Auth guard
  useEffect(() => {
    if (!authLoading && user && !user.isAdmin && !user.isDraftManager) {
      router.push("/");
    }
  }, [user, authLoading, router]);

  // Load drafts list
  const loadDrafts = useCallback(async () => {
    if (!selectedSeason) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<DraftListResponse>(
        `/drafts/${selectedSeason.id}`,
      );
      setDrafts(data);
    } catch {
      setError("Error cargando drafts");
    } finally {
      setLoading(false);
    }
  }, [selectedSeason]);

  useEffect(() => {
    loadDrafts();
  }, [loadDrafts]);

  // Load draft detail (participants come from here)
  const loadDraftDetail = useCallback(async () => {
    if (!selectedSeason || !drafts) return;
    const draft = drafts.drafts.find((d) => d.phase === selectedPhase);
    if (!draft) {
      setDraftDetail(null);
      setLocalPicks([]);
      setEditableParticipants([]);
      return;
    }
    try {
      const detail = await apiClient.get<DraftDetailResponse>(
        `/drafts/${selectedSeason.id}/${selectedPhase}`,
      );
      setDraftDetail(detail);
      setLocalPicks(detail.picks);
      setEditableParticipants(
        [...detail.participants].sort(
          (a, b) => (a.draft_order ?? 999) - (b.draft_order ?? 999),
        ),
      );
      setHasReorderChanges(false);
      setFilterParticipantId(null);
    } catch {
      setDraftDetail(null);
      setLocalPicks([]);
      setEditableParticipants([]);
    }
  }, [selectedSeason, drafts, selectedPhase]);

  useEffect(() => {
    loadDraftDetail();
  }, [loadDraftDetail]);

  // --- Participant order ---
  function moveParticipant(index: number, direction: -1 | 1) {
    const newList = [...editableParticipants];
    const target = index + direction;
    if (target < 0 || target >= newList.length) return;
    [newList[index], newList[target]] = [newList[target], newList[index]];
    setEditableParticipants(
      newList.map((p, i) => ({ ...p, draft_order: i + 1 })),
    );
  }

  async function saveOrder() {
    if (!selectedSeason) return;
    setLoading(true);
    setError(null);
    try {
      await apiClient.put(`/drafts/${selectedSeason.id}/participants/order`, {
        orders: editableParticipants.map((p) => ({
          participant_id: p.participant_id,
          draft_order: p.draft_order,
        })),
      });
      showSuccess("Orden guardado");
      await loadDraftDetail();
    } catch {
      setError("Error guardando orden");
    } finally {
      setLoading(false);
    }
  }

  // --- Create draft ---
  async function createDraft(phase: string, draftType: string) {
    if (!selectedSeason) return;
    setLoading(true);
    setError(null);
    try {
      await apiClient.post<CreateDraftResponse>(
        `/drafts/${selectedSeason.id}`,
        { phase, draft_type: draftType },
      );
      showSuccess(`Draft ${PHASE_LABELS[phase]} creado`);
      await loadDrafts();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando draft");
    } finally {
      setLoading(false);
    }
  }

  // --- Drag and drop ---
  function handleDragStart(e: React.DragEvent, index: number) {
    setDragIndex(index);
    dragNodeRef.current = e.currentTarget as HTMLDivElement;
    // Required for Firefox
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(index));
    // Slight delay so the dragged element renders before opacity change
    requestAnimationFrame(() => {
      if (dragNodeRef.current) {
        dragNodeRef.current.style.opacity = "0.4";
      }
    });
  }

  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dragOverIndex !== index) {
      setDragOverIndex(index);
    }
  }

  function handleDrop(e: React.DragEvent, targetIndex: number) {
    e.preventDefault();
    if (dragIndex === null || dragIndex === targetIndex) {
      resetDrag();
      return;
    }

    const newPicks = [...localPicks];
    const [moved] = newPicks.splice(dragIndex, 1);
    newPicks.splice(targetIndex, 0, moved);
    recalculatePicks(newPicks);
    resetDrag();
  }

  function handleDragEnd() {
    if (dragNodeRef.current) {
      dragNodeRef.current.style.opacity = "1";
    }
    resetDrag();
  }

  function resetDrag() {
    setDragIndex(null);
    setDragOverIndex(null);
    dragNodeRef.current = null;
  }

  // --- Move pick up/down ---
  function movePick(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= localPicks.length) return;
    const newPicks = [...localPicks];
    [newPicks[index], newPicks[target]] = [newPicks[target], newPicks[index]];
    recalculatePicks(newPicks);
  }

  // --- Recalculate pick numbers and rounds (participant stays the same) ---
  function recalculatePicks(newPicks: DraftPickEntry[]) {
    const n = orderedParticipants.length || 1;
    const isWinter = selectedPhase === "winter";

    const recalculated = newPicks.map((pick, i) => ({
      ...pick,
      pick_number: i + 1,
      // Winter = single round of trades; preseason = rounds based on participant count
      round_number: isWinter ? 1 : Math.floor(i / n) + 1,
      // participant_id is NOT recalculated — it's who actually picked the player
    }));

    setLocalPicks(recalculated);
    setHasReorderChanges(true);
  }

  // --- Save reorder ---
  async function saveReorder() {
    const draftId = drafts?.drafts.find((d) => d.phase === selectedPhase)?.id;
    if (!draftId) return;
    setSavingReorder(true);
    setError(null);
    try {
      await apiClient.put(`/drafts/${draftId}/picks/reorder`, {
        pick_ids: localPicks.map((p) => p.id),
      });
      showSuccess("Orden de picks guardado");
      setHasReorderChanges(false);
      await loadDraftDetail();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error guardando orden");
    } finally {
      setSavingReorder(false);
    }
  }

  function cancelReorder() {
    if (draftDetail) {
      setLocalPicks(draftDetail.picks);
    }
    setHasReorderChanges(false);
  }

  function showSuccess(msg: string) {
    setSuccess(msg);
    setTimeout(() => setSuccess(null), 3000);
  }

  if (authLoading || seasonLoading) {
    return <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />;
  }

  if (!user || (!user.isAdmin && !user.isDraftManager)) {
    return null;
  }

  const currentDraft = drafts?.drafts.find((d) => d.phase === selectedPhase);

  // Filter picks: when a participant is selected, show only their picks
  const displayPicks = filterParticipantId
    ? localPicks.filter((p) => p.participant_id === filterParticipantId)
    : localPicks;

  // Whether drag/reorder is allowed (not when filtering)
  const canReorder = !filterParticipantId;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">Gestionar Draft</h1>
        <SeasonSelector />
      </div>

      {/* Messages */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-3 text-sm text-green-400">
          {success}
        </div>
      )}

      {loading && (
        <div className="text-sm text-vpv-text-muted">Cargando...</div>
      )}

      {/* Phase selector */}
      <div className="flex gap-2">
        {["preseason", "winter"].map((phase) => (
          <button
            key={phase}
            onClick={() => setSelectedPhase(phase)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              selectedPhase === phase
                ? "bg-vpv-accent text-white"
                : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {PHASE_LABELS[phase]}
          </button>
        ))}
      </div>

      {/* Step 1: Participant order */}
      {draftDetail && (
        <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
          <h2 className="mb-4 text-lg font-semibold text-vpv-text">
            1. Orden del Draft
          </h2>
          {editableParticipants.length === 0 ? (
            <p className="text-sm text-vpv-text-muted">
              No hay participantes en esta temporada.
            </p>
          ) : (
            <>
              <ul className="space-y-1">
                {editableParticipants.map((p, i) => {
                  const colors = getColorForParticipant(p.participant_id, participants);
                  return (
                    <li
                      key={p.participant_id}
                      className={`flex items-center gap-3 rounded-lg border-l-4 bg-vpv-bg px-4 py-2 ${colors.border}`}
                    >
                      <span className="w-8 text-center text-sm font-bold text-vpv-accent">
                        {p.draft_order ?? i + 1}
                      </span>
                      <span className="flex-1 text-sm text-vpv-text">
                        {p.display_name}
                      </span>
                      <button
                        onClick={() => moveParticipant(i, -1)}
                        disabled={i === 0}
                        className="rounded p-1 text-vpv-text-muted hover:text-vpv-text disabled:opacity-30"
                        title="Subir"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                          <path fillRule="evenodd" d="M14.77 12.79a.75.75 0 01-1.06-.02L10 8.832 6.29 12.77a.75.75 0 11-1.08-1.04l4.25-4.5a.75.75 0 011.08 0l4.25 4.5a.75.75 0 01-.02 1.06z" clipRule="evenodd" />
                        </svg>
                      </button>
                      <button
                        onClick={() => moveParticipant(i, 1)}
                        disabled={i === editableParticipants.length - 1}
                        className="rounded p-1 text-vpv-text-muted hover:text-vpv-text disabled:opacity-30"
                        title="Bajar"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </li>
                  );
                })}
              </ul>
              <button
                onClick={saveOrder}
                disabled={loading}
                className="mt-3 rounded-lg bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
              >
                Guardar orden
              </button>
            </>
          )}
        </section>
      )}

      {/* Step 2: Create draft if it doesn't exist */}
      {!currentDraft && (
        <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
          <h2 className="mb-4 text-lg font-semibold text-vpv-text">
            2. Crear Draft ({PHASE_LABELS[selectedPhase]})
          </h2>
          <div className="flex gap-3">
            <button
              onClick={() => createDraft(selectedPhase, "snake")}
              disabled={loading}
              className="rounded-lg bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
            >
              Crear Serpiente
            </button>
            <button
              onClick={() => createDraft(selectedPhase, "linear")}
              disabled={loading}
              className="rounded-lg border border-vpv-accent px-4 py-2 text-sm font-medium text-vpv-accent transition-colors hover:bg-vpv-accent/10 disabled:opacity-50"
            >
              Crear Lineal
            </button>
          </div>
        </section>
      )}

      {/* Step 3: Picks reorder */}
      {currentDraft && draftDetail && (
        <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-vpv-text">
                2. Picks
              </h2>
              <p className="text-xs text-vpv-text-muted">
                {PHASE_LABELS[selectedPhase]} &middot;{" "}
                {TYPE_LABELS[currentDraft.draft_type]} &middot;{" "}
                {localPicks.length} picks
                {canReorder && " \u00b7 Arrastra o usa flechas para reordenar"}
              </p>
            </div>
            {hasReorderChanges && (
              <div className="flex gap-2">
                <button
                  onClick={cancelReorder}
                  className="rounded-lg border border-vpv-border px-4 py-2 text-sm font-medium text-vpv-text-muted transition-colors hover:text-vpv-text"
                >
                  Cancelar
                </button>
                <button
                  onClick={saveReorder}
                  disabled={savingReorder}
                  className="rounded-lg bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
                >
                  {savingReorder ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            )}
          </div>

          {/* Filter by participant */}
          <div className="mb-4 flex flex-wrap gap-2">
            <button
              onClick={() => setFilterParticipantId(null)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                filterParticipantId === null
                  ? "bg-vpv-accent text-white"
                  : "bg-vpv-bg text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              Todos ({localPicks.length})
            </button>
            {orderedParticipants.map((p) => {
              const count = localPicks.filter(
                (pk) => pk.participant_id === p.participant_id,
              ).length;
              const colors = getColorForParticipant(p.participant_id, participants);
              const isActive = filterParticipantId === p.participant_id;
              return (
                <button
                  key={p.participant_id}
                  onClick={() =>
                    setFilterParticipantId(isActive ? null : p.participant_id)
                  }
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-vpv-accent text-white"
                      : `${colors.bg} ${colors.text} hover:brightness-125`
                  }`}
                >
                  {p.display_name} ({count})
                </button>
              );
            })}
          </div>

          {filterParticipantId && (
            <div className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-400">
              Mostrando picks de {participants.find((p) => p.participant_id === filterParticipantId)?.display_name}.
              Reordenar deshabilitado mientras filtras.
            </div>
          )}

          {/* Picks list */}
          {displayPicks.length === 0 ? (
            <p className="py-8 text-center text-sm text-vpv-text-muted">
              {localPicks.length === 0
                ? "No hay picks registrados todav\u00eda."
                : "Sin picks para este participante."}
            </p>
          ) : (
            <div className="space-y-px">
              {displayPicks.map((pick, displayIdx) => {
                const isWinter = selectedPhase === "winter";

                // Separator: preseason = by round, winter = by participant
                const isFirstOfGroup = isWinter
                  ? displayIdx === 0 ||
                    displayPicks[displayIdx - 1].participant_id !== pick.participant_id
                  : displayIdx === 0 ||
                    displayPicks[displayIdx - 1].round_number !== pick.round_number;

                // When filtering, we can't reorder so globalIdx doesn't matter for drag
                const globalIdx = filterParticipantId
                  ? localPicks.findIndex((p) => p.id === pick.id)
                  : displayIdx;

                const isDragOver = dragOverIndex === globalIdx && canReorder;
                const colors = getColorForParticipant(pick.participant_id, participants);

                return (
                  <div key={pick.id}>
                    {isFirstOfGroup && (
                      <div className="pb-1 pt-4 first:pt-0">
                        <span className={`text-xs font-semibold uppercase tracking-wider ${isWinter ? colors.text : "text-vpv-text-muted"}`}>
                          {isWinter ? pick.display_name : `Ronda ${pick.round_number}`}
                        </span>
                      </div>
                    )}
                    <div
                      draggable={canReorder}
                      onDragStart={(e) => canReorder && handleDragStart(e, globalIdx)}
                      onDragOver={(e) => canReorder && handleDragOver(e, globalIdx)}
                      onDrop={(e) => canReorder && handleDrop(e, globalIdx)}
                      onDragEnd={handleDragEnd}
                      className={`group flex items-center gap-2 rounded-lg border-l-4 px-3 py-2.5 text-sm transition-all sm:gap-3 ${colors.border} ${
                        isDragOver
                          ? "bg-vpv-accent/10 ring-2 ring-vpv-accent/40"
                          : "bg-vpv-bg hover:bg-vpv-bg/80"
                      } ${canReorder ? "cursor-grab active:cursor-grabbing" : ""}`}
                    >
                      {/* Grip handle (desktop only, only when can reorder) */}
                      {canReorder && (
                        <span className="hidden flex-shrink-0 text-vpv-text-muted/40 group-hover:text-vpv-text-muted sm:block">
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
                            <path fillRule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm0 5.5a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75zm.75 4.75a.75.75 0 000 1.5h14.5a.75.75 0 000-1.5H2.75z" clipRule="evenodd" />
                          </svg>
                        </span>
                      )}

                      {/* Pick number */}
                      <span className="w-7 flex-shrink-0 text-center text-xs font-bold text-vpv-accent">
                        #{pick.pick_number}
                      </span>

                      {/* Move arrows (always visible, only when can reorder) */}
                      {canReorder && (
                        <div className="flex flex-shrink-0 flex-col gap-0.5">
                          <button
                            onClick={(e) => { e.stopPropagation(); movePick(globalIdx, -1); }}
                            disabled={globalIdx === 0}
                            className="rounded p-0.5 text-vpv-text-muted hover:bg-vpv-card hover:text-vpv-text disabled:opacity-20"
                            title="Subir pick"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                              <path fillRule="evenodd" d="M11.78 9.78a.75.75 0 0 1-1.06 0L8 7.06 5.28 9.78a.75.75 0 0 1-1.06-1.06l3.25-3.25a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06Z" clipRule="evenodd" />
                            </svg>
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); movePick(globalIdx, 1); }}
                            disabled={globalIdx === localPicks.length - 1}
                            className="rounded p-0.5 text-vpv-text-muted hover:bg-vpv-card hover:text-vpv-text disabled:opacity-20"
                            title="Bajar pick"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                              <path fillRule="evenodd" d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                            </svg>
                          </button>
                        </div>
                      )}

                      {/* Position badge */}
                      <span
                        className={`flex-shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${POS_COLORS[pick.position] ?? ""}`}
                      >
                        {pick.position}
                      </span>

                      {/* Player name + dropped player for winter */}
                      <div className="min-w-0 flex-1">
                        <span className="truncate font-medium text-vpv-text">
                          {pick.player_name}
                        </span>
                        {isWinter && pick.dropped_player_name && (
                          <span className="ml-1.5 text-[10px] text-red-400/70">
                            &larr; {pick.dropped_player_name}
                          </span>
                        )}
                      </div>

                      {/* Team (hidden on mobile) */}
                      <span className="hidden flex-shrink-0 text-xs text-vpv-text-muted md:inline">
                        {pick.team_name}
                      </span>

                      {/* Participant badge (hidden in winter when not filtering, since grouped by participant) */}
                      {(!isWinter || filterParticipantId) && (
                        <span className={`flex-shrink-0 truncate rounded-full px-2 py-0.5 text-[10px] font-medium ${colors.bg} ${colors.text}`}>
                          {pick.display_name}
                        </span>
                      )}

                      {/* Round indicator (preseason only) */}
                      {!isWinter && (
                        <span className="w-8 flex-shrink-0 text-center text-[10px] text-vpv-text-muted">
                          R{pick.round_number}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Bottom save bar (sticky when scrolling long lists) */}
          {hasReorderChanges && displayPicks.length > 10 && (
            <div className="sticky bottom-0 mt-4 flex justify-end gap-2 rounded-lg border border-vpv-card-border bg-vpv-card/95 px-4 py-3 backdrop-blur-sm">
              <button
                onClick={cancelReorder}
                className="rounded-lg border border-vpv-border px-4 py-2 text-sm font-medium text-vpv-text-muted transition-colors hover:text-vpv-text"
              >
                Cancelar
              </button>
              <button
                onClick={saveReorder}
                disabled={savingReorder}
                className="rounded-lg bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
              >
                {savingReorder ? "Guardando..." : "Guardar cambios"}
              </button>
            </div>
          )}
        </section>
      )}

      {/* Load participants for ordering when no draft exists yet */}
      {!currentDraft && !draftDetail && selectedSeason && (
        <ParticipantOrderStandalone seasonId={selectedSeason.id} />
      )}
    </div>
  );
}

/** Standalone participant order when no draft exists yet */
function ParticipantOrderStandalone({ seasonId }: { seasonId: number }) {
  const [participants, setParticipants] = useState<DraftParticipant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        // Try loading from any existing draft
        for (const phase of ["preseason", "winter"]) {
          try {
            const detail = await apiClient.get<DraftDetailResponse>(
              `/drafts/${seasonId}/${phase}`,
            );
            setParticipants(
              [...detail.participants].sort(
                (a, b) => (a.draft_order ?? 999) - (b.draft_order ?? 999),
              ),
            );
            return;
          } catch {
            // continue
          }
        }
        setParticipants([]);
      } catch {
        setError("Error cargando participantes");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [seasonId]);

  function moveParticipant(index: number, direction: -1 | 1) {
    const newList = [...participants];
    const target = index + direction;
    if (target < 0 || target >= newList.length) return;
    [newList[index], newList[target]] = [newList[target], newList[index]];
    setParticipants(newList.map((p, i) => ({ ...p, draft_order: i + 1 })));
  }

  async function saveOrder() {
    setLoading(true);
    setError(null);
    try {
      await apiClient.put(`/drafts/${seasonId}/participants/order`, {
        orders: participants.map((p) => ({
          participant_id: p.participant_id,
          draft_order: p.draft_order,
        })),
      });
      setSuccess("Orden guardado");
      setTimeout(() => setSuccess(null), 3000);
    } catch {
      setError("Error guardando orden");
    } finally {
      setLoading(false);
    }
  }

  if (loading) return null;
  if (participants.length === 0) return null;

  return (
    <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
      <h2 className="mb-4 text-lg font-semibold text-vpv-text">
        1. Orden del Draft
      </h2>
      {error && (
        <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">{error}</div>
      )}
      {success && (
        <div className="mb-3 rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-2 text-sm text-green-400">{success}</div>
      )}
      <ul className="space-y-1">
        {participants.map((p, i) => (
          <li
            key={p.participant_id}
            className="flex items-center gap-3 rounded-lg border-l-4 border-l-vpv-accent/30 bg-vpv-bg px-4 py-2"
          >
            <span className="w-8 text-center text-sm font-bold text-vpv-accent">
              {p.draft_order ?? i + 1}
            </span>
            <span className="flex-1 text-sm text-vpv-text">{p.display_name}</span>
            <button
              onClick={() => moveParticipant(i, -1)}
              disabled={i === 0}
              className="rounded p-1 text-vpv-text-muted hover:text-vpv-text disabled:opacity-30"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path fillRule="evenodd" d="M14.77 12.79a.75.75 0 01-1.06-.02L10 8.832 6.29 12.77a.75.75 0 11-1.08-1.04l4.25-4.5a.75.75 0 011.08 0l4.25 4.5a.75.75 0 01-.02 1.06z" clipRule="evenodd" />
              </svg>
            </button>
            <button
              onClick={() => moveParticipant(i, 1)}
              disabled={i === participants.length - 1}
              className="rounded p-1 text-vpv-text-muted hover:text-vpv-text disabled:opacity-30"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
              </svg>
            </button>
          </li>
        ))}
      </ul>
      <button
        onClick={saveOrder}
        disabled={loading}
        className="mt-3 rounded-lg bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
      >
        Guardar orden
      </button>
    </section>
  );
}
