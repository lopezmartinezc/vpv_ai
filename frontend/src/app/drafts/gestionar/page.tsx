"use client";

import { useCallback, useEffect, useState } from "react";
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
  "border-l-blue-500",
  "border-l-emerald-500",
  "border-l-amber-500",
  "border-l-red-500",
  "border-l-purple-500",
  "border-l-cyan-500",
  "border-l-pink-500",
  "border-l-orange-500",
  "border-l-lime-500",
  "border-l-indigo-500",
  "border-l-teal-500",
];
const PARTICIPANT_BG = [
  "bg-blue-500/10",
  "bg-emerald-500/10",
  "bg-amber-500/10",
  "bg-red-500/10",
  "bg-purple-500/10",
  "bg-cyan-500/10",
  "bg-pink-500/10",
  "bg-orange-500/10",
  "bg-lime-500/10",
  "bg-indigo-500/10",
  "bg-teal-500/10",
];

function getParticipantForPick(
  pickNumber: number,
  draftType: string,
  orderedParticipants: DraftParticipant[],
): DraftParticipant | undefined {
  const n = orderedParticipants.length;
  if (n === 0) return undefined;
  const round = Math.floor((pickNumber - 1) / n) + 1;
  let posInRound = (pickNumber - 1) % n;
  if (draftType === "snake" && round % 2 === 0) {
    posInRound = n - 1 - posInRound;
  }
  return orderedParticipants[posInRound];
}

export default function GestionarDraftPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason, loading: seasonLoading } = useSeason();

  const [drafts, setDrafts] = useState<DraftListResponse | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<string>("preseason");
  const [draftDetail, setDraftDetail] = useState<DraftDetailResponse | null>(
    null,
  );
  const [participants, setParticipants] = useState<DraftParticipant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Pick reorder state
  const [filterParticipantId, setFilterParticipantId] = useState<number | null>(
    null,
  );
  const [localPicks, setLocalPicks] = useState<DraftPickEntry[]>([]);
  const [hasReorderChanges, setHasReorderChanges] = useState(false);
  const [savingReorder, setSavingReorder] = useState(false);

  // Drag state
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // Auth guard
  useEffect(() => {
    if (!authLoading && user && !user.isAdmin && !user.isDraftManager) {
      router.push("/");
    }
  }, [user, authLoading, router]);

  const participantColorMap = useCallback(() => {
    const map: Record<number, number> = {};
    participants.forEach((p, i) => {
      map[p.participant_id] = i % PARTICIPANT_COLORS.length;
    });
    return map;
  }, [participants]);

  // Load drafts
  const loadDrafts = useCallback(async () => {
    if (!selectedSeason) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<DraftListResponse>(
        `/drafts/${selectedSeason.id}`,
      );
      setDrafts(data);
      const parts = await loadParticipants(selectedSeason.id);
      setParticipants(parts);
    } catch {
      setError("Error cargando drafts");
    } finally {
      setLoading(false);
    }
  }, [selectedSeason]);

  useEffect(() => {
    loadDrafts();
  }, [loadDrafts]);

  async function loadParticipants(
    seasonId: number,
  ): Promise<DraftParticipant[]> {
    try {
      const detail = await apiClient.get<DraftDetailResponse>(
        `/drafts/${seasonId}/preseason`,
      );
      return detail.participants;
    } catch {
      try {
        const detail = await apiClient.get<DraftDetailResponse>(
          `/drafts/${seasonId}/winter`,
        );
        return detail.participants;
      } catch {
        return [];
      }
    }
  }

  // Load draft detail
  const loadDraftDetail = useCallback(async () => {
    if (!selectedSeason || !drafts) return;
    const draft = drafts.drafts.find((d) => d.phase === selectedPhase);
    if (!draft) {
      setDraftDetail(null);
      setLocalPicks([]);
      return;
    }
    try {
      const detail = await apiClient.get<DraftDetailResponse>(
        `/drafts/${selectedSeason.id}/${selectedPhase}`,
      );
      setDraftDetail(detail);
      setLocalPicks(detail.picks);
      setHasReorderChanges(false);
    } catch {
      setDraftDetail(null);
      setLocalPicks([]);
    }
  }, [selectedSeason, drafts, selectedPhase]);

  useEffect(() => {
    loadDraftDetail();
  }, [loadDraftDetail]);

  // --- Participant order ---
  function moveParticipant(index: number, direction: -1 | 1) {
    const newList = [...participants];
    const target = index + direction;
    if (target < 0 || target >= newList.length) return;
    [newList[index], newList[target]] = [newList[target], newList[index]];
    setParticipants(
      newList.map((p, i) => ({ ...p, draft_order: i + 1 })),
    );
  }

  async function saveOrder() {
    if (!selectedSeason) return;
    setLoading(true);
    setError(null);
    try {
      await apiClient.put(`/drafts/${selectedSeason.id}/participants/order`, {
        orders: participants.map((p) => ({
          participant_id: p.participant_id,
          draft_order: p.draft_order,
        })),
      });
      showSuccess("Orden guardado");
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

  // --- Drag and drop reorder ---
  function handleDragStart(index: number) {
    setDragIndex(index);
  }

  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault();
    setDragOverIndex(index);
  }

  function handleDrop(targetIndex: number) {
    if (dragIndex === null || dragIndex === targetIndex) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }

    const newPicks = [...localPicks];
    const [moved] = newPicks.splice(dragIndex, 1);
    newPicks.splice(targetIndex, 0, moved);

    recalculatePicks(newPicks);
    setDragIndex(null);
    setDragOverIndex(null);
  }

  function handleDragEnd() {
    setDragIndex(null);
    setDragOverIndex(null);
  }

  // --- Move pick up/down (alternative to drag) ---
  function movePick(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= localPicks.length) return;
    const newPicks = [...localPicks];
    [newPicks[index], newPicks[target]] = [newPicks[target], newPicks[index]];
    recalculatePicks(newPicks);
  }

  // --- Edit round number manually ---
  function setPickRound(index: number, newRound: number) {
    if (newRound < 1) return;
    const updated = [...localPicks];
    updated[index] = { ...updated[index], round_number: newRound };
    setLocalPicks(updated);
    setHasReorderChanges(true);
  }

  // --- Recalculate pick numbers and participant assignments ---
  function recalculatePicks(newPicks: DraftPickEntry[]) {
    const numParticipants = participants.length || 1;
    const activeDraft = drafts?.drafts.find((d) => d.phase === selectedPhase);
    const draftType = activeDraft?.draft_type ?? "snake";
    const orderedParts = [...participants].sort(
      (a, b) => (a.draft_order ?? 999) - (b.draft_order ?? 999),
    );

    const recalculated = newPicks.map((pick, i) => {
      const pickNumber = i + 1;
      const assignedParticipant = getParticipantForPick(
        pickNumber,
        draftType,
        orderedParts,
      );
      return {
        ...pick,
        pick_number: pickNumber,
        round_number: Math.floor(i / numParticipants) + 1,
        participant_id:
          assignedParticipant?.participant_id ?? pick.participant_id,
        display_name: assignedParticipant?.display_name ?? pick.display_name,
        draft_order: assignedParticipant?.draft_order ?? pick.draft_order,
      };
    });

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
  const colorMap = participantColorMap();

  const displayPicks = filterParticipantId
    ? localPicks.filter((p) => p.participant_id === filterParticipantId)
    : localPicks;

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
      <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
        <h2 className="mb-4 text-lg font-semibold text-vpv-text">
          1. Orden del Draft
        </h2>
        {participants.length === 0 ? (
          <p className="text-sm text-vpv-text-muted">
            No hay participantes en esta temporada.
          </p>
        ) : (
          <>
            <ul className="space-y-1">
              {participants.map((p, i) => (
                <li
                  key={p.participant_id}
                  className={`flex items-center gap-3 rounded-lg border-l-4 bg-vpv-bg px-4 py-2 ${
                    PARTICIPANT_COLORS[colorMap[p.participant_id] ?? 0]
                  }`}
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
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="h-4 w-4"
                    >
                      <path
                        fillRule="evenodd"
                        d="M14.77 12.79a.75.75 0 01-1.06-.02L10 8.832 6.29 12.77a.75.75 0 11-1.08-1.04l4.25-4.5a.75.75 0 011.08 0l4.25 4.5a.75.75 0 01-.02 1.06z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </button>
                  <button
                    onClick={() => moveParticipant(i, 1)}
                    disabled={i === participants.length - 1}
                    className="rounded p-1 text-vpv-text-muted hover:text-vpv-text disabled:opacity-30"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="h-4 w-4"
                    >
                      <path
                        fillRule="evenodd"
                        d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                        clipRule="evenodd"
                      />
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
          </>
        )}
      </section>

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
      {currentDraft && (
        <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-vpv-text">
                3. Reordenar Picks
              </h2>
              <p className="text-xs text-vpv-text-muted">
                {PHASE_LABELS[selectedPhase]} &middot;{" "}
                {TYPE_LABELS[currentDraft.draft_type]} &middot;{" "}
                {localPicks.length} picks &middot; Arrastra o usa las flechas
                para mover
              </p>
            </div>
            {hasReorderChanges && (
              <div className="flex gap-2">
                <button
                  onClick={cancelReorder}
                  className="rounded-lg border border-vpv-border px-3 py-1.5 text-xs font-medium text-vpv-text-muted transition-colors hover:text-vpv-text"
                >
                  Cancelar
                </button>
                <button
                  onClick={saveReorder}
                  disabled={savingReorder}
                  className="rounded-lg bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
                >
                  {savingReorder ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            )}
          </div>

          {/* Filter by participant */}
          <div className="mb-3 flex flex-wrap gap-1.5">
            <button
              onClick={() => setFilterParticipantId(null)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                filterParticipantId === null
                  ? "bg-vpv-accent text-white"
                  : "bg-vpv-bg text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              Todos ({localPicks.length})
            </button>
            {participants.map((p) => {
              const count = localPicks.filter(
                (pk) => pk.participant_id === p.participant_id,
              ).length;
              return (
                <button
                  key={p.participant_id}
                  onClick={() =>
                    setFilterParticipantId(
                      filterParticipantId === p.participant_id
                        ? null
                        : p.participant_id,
                    )
                  }
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    filterParticipantId === p.participant_id
                      ? "bg-vpv-accent text-white"
                      : `${PARTICIPANT_BG[colorMap[p.participant_id] ?? 0]} text-vpv-text-muted hover:text-vpv-text`
                  }`}
                >
                  {p.display_name} ({count})
                </button>
              );
            })}
          </div>

          {/* Picks list */}
          {displayPicks.length === 0 ? (
            <p className="py-4 text-center text-sm text-vpv-text-muted">
              {localPicks.length === 0
                ? "No hay picks registrados todavia."
                : "Sin picks para este participante."}
            </p>
          ) : (
            <div className="space-y-0.5">
              {displayPicks.map((pick, displayIdx) => {
                const isFirstOfRound =
                  displayIdx === 0 ||
                  displayPicks[displayIdx - 1].round_number !==
                    pick.round_number;
                const globalIdx = filterParticipantId
                  ? localPicks.findIndex((p) => p.id === pick.id)
                  : displayIdx;
                const isDragging = dragIndex === globalIdx;
                const isDragOver = dragOverIndex === globalIdx;
                const canDrag = !filterParticipantId;

                return (
                  <div key={pick.id}>
                    {isFirstOfRound && (
                      <div className="pb-0.5 pt-3 first:pt-0">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
                          Ronda {pick.round_number}
                        </span>
                      </div>
                    )}
                    <div
                      draggable={canDrag}
                      onDragStart={() => canDrag && handleDragStart(globalIdx)}
                      onDragOver={(e) =>
                        canDrag && handleDragOver(e, globalIdx)
                      }
                      onDrop={() => canDrag && handleDrop(globalIdx)}
                      onDragEnd={handleDragEnd}
                      className={`flex items-center gap-2 rounded-lg border-l-4 px-3 py-2 text-sm transition-all ${
                        PARTICIPANT_COLORS[
                          colorMap[pick.participant_id] ?? 0
                        ]
                      } ${
                        isDragging
                          ? "opacity-40"
                          : isDragOver
                            ? "bg-vpv-accent/10 ring-1 ring-vpv-accent/30"
                            : "bg-vpv-bg"
                      } ${canDrag ? "cursor-grab active:cursor-grabbing" : ""}`}
                    >
                      {/* Pick number */}
                      <span className="w-7 flex-shrink-0 text-center text-xs font-bold text-vpv-accent">
                        {pick.pick_number}
                      </span>

                      {/* Move arrows */}
                      <div className="flex flex-shrink-0 flex-col">
                        <button
                          onClick={() => movePick(globalIdx, -1)}
                          disabled={globalIdx === 0 || !!filterParticipantId}
                          className="text-vpv-text-muted/50 hover:text-vpv-text disabled:opacity-20"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 16 16"
                            fill="currentColor"
                            className="h-3 w-3"
                          >
                            <path
                              fillRule="evenodd"
                              d="M11.78 9.78a.75.75 0 0 1-1.06 0L8 7.06 5.28 9.78a.75.75 0 0 1-1.06-1.06l3.25-3.25a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06Z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </button>
                        <button
                          onClick={() => movePick(globalIdx, 1)}
                          disabled={
                            globalIdx === localPicks.length - 1 ||
                            !!filterParticipantId
                          }
                          className="text-vpv-text-muted/50 hover:text-vpv-text disabled:opacity-20"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 16 16"
                            fill="currentColor"
                            className="h-3 w-3"
                          >
                            <path
                              fillRule="evenodd"
                              d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </button>
                      </div>

                      {/* Position badge */}
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${POS_COLORS[pick.position] ?? ""}`}
                      >
                        {pick.position}
                      </span>

                      {/* Player name */}
                      <span className="flex-1 truncate font-medium text-vpv-text">
                        {pick.player_name}
                      </span>

                      {/* Team */}
                      <span className="hidden text-xs text-vpv-text-muted sm:inline">
                        {pick.team_name}
                      </span>

                      {/* Participant name */}
                      <span className="truncate text-xs text-vpv-text-muted">
                        {pick.display_name}
                      </span>

                      {/* Editable round */}
                      <div className="flex flex-shrink-0 items-center gap-1">
                        <span className="text-[10px] text-vpv-text-muted">
                          R
                        </span>
                        <input
                          type="number"
                          min={1}
                          value={pick.round_number}
                          onChange={(e) =>
                            setPickRound(globalIdx, parseInt(e.target.value) || 1)
                          }
                          className="w-8 rounded border border-vpv-border bg-vpv-card px-1 py-0.5 text-center text-[10px] text-vpv-text"
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
