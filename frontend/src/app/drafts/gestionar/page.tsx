"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { apiClient } from "@/lib/api-client";
import { SeasonSelector } from "@/components/layout/season-selector";
import { PERM, userHasPerm } from "@/lib/permissions";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type {
  CreateDraftResponse,
  DraftDetailResponse,
  DraftListResponse,
  DraftParticipant,
  DraftPickEntry,
  PlayerSearchItem,
  PlayerSearchResponse,
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
  const { selectedSeason, isTournamentContext, loading: seasonLoading } = useSeason();

  const [drafts, setDrafts] = useState<DraftListResponse | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<string>("preseason");
  const [draftDetail, setDraftDetail] = useState<DraftDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Participants from draft detail
  const participants = draftDetail?.participants ?? [];
  const orderedParticipants = [...participants].sort(
    (a, b) => (a.draft_order ?? 999) - (b.draft_order ?? 999),
  );

  // Pick reorder state
  const [filterParticipantId, setFilterParticipantId] = useState<number | null>(null);
  const [localPicks, setLocalPicks] = useState<DraftPickEntry[]>([]);
  const [hasReorderChanges, setHasReorderChanges] = useState(false);
  const [savingReorder, setSavingReorder] = useState(false);
  // Manual round edits: pick.id -> edited round number (not yet applied)
  const [editedRounds, setEditedRounds] = useState<Record<number, number>>({});
  const [roundError, setRoundError] = useState<string | null>(null);

  // Drag state (indices always refer to displayPicks)
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const dragNodeRef = useRef<HTMLDivElement | null>(null);

  // Participant order (editable copy)
  const [editableParticipants, setEditableParticipants] = useState<DraftParticipant[]>([]);

  // Manual pick add (admin) — search + filters
  const [addSearch, setAddSearch] = useState("");
  const [addPosFilter, setAddPosFilter] = useState("");
  const [addTeamFilter, setAddTeamFilter] = useState("");
  const [addResults, setAddResults] = useState<PlayerSearchItem[]>([]);
  const [addSearching, setAddSearching] = useState(false);
  const [addingPick, setAddingPick] = useState(false);
  // Target participant for the manual add. When the participant-filter
  // pill is active, we inherit it; otherwise it's an explicit choice.
  const [addTargetParticipantId, setAddTargetParticipantId] = useState<
    number | null
  >(null);

  const isWinter = selectedPhase === "winter";

  // Auth guard
  useEffect(() => {
    if (!authLoading && user && !user.isAdmin && !userHasPerm(user.isAdmin, user.permissions, PERM.DRAFT)) {
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
      setEditedRounds({});
      setRoundError(null);
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

  // Filtered picks for display
  const displayPicks = filterParticipantId
    ? localPicks.filter((p) => p.participant_id === filterParticipantId)
    : localPicks;

  // --- Core reorder: applies a new filtered order back to global picks ---
  function applyReorder(newDisplayOrder: DraftPickEntry[]) {
    if (!filterParticipantId) {
      // No filter: newDisplayOrder IS the new global order
      recalculateGlobal(newDisplayOrder);
    } else {
      // With filter: put reordered picks back at their original global slots
      const participantSlots: number[] = [];
      localPicks.forEach((p, i) => {
        if (p.participant_id === filterParticipantId) {
          participantSlots.push(i);
        }
      });

      const newGlobal = [...localPicks];
      participantSlots.forEach((globalIdx, i) => {
        newGlobal[globalIdx] = newDisplayOrder[i];
      });
      recalculateGlobal(newGlobal);
    }
  }

  // Recalculate pick_number and round_number for all picks
  // Within each round, picks are sorted by draft_order (snake reverses even rounds)
  function recalculateGlobal(newPicks: DraftPickEntry[]) {
    const n = orderedParticipants.length || 1;

    if (isWinter) {
      setLocalPicks(
        newPicks.map((pick, i) => ({ ...pick, pick_number: i + 1, round_number: 1 })),
      );
      setHasReorderChanges(true);
      return;
    }

    // Step 1: assign round numbers based on position
    const withRounds = newPicks.map((pick, i) => ({
      ...pick,
      round_number: Math.floor(i / n) + 1,
    }));

    // Step 2: group by round, sort within round by draft_order
    const draftType = draftDetail?.draft_type ?? "snake";
    const roundMap = new Map<number, DraftPickEntry[]>();
    for (const pick of withRounds) {
      if (!roundMap.has(pick.round_number)) roundMap.set(pick.round_number, []);
      roundMap.get(pick.round_number)!.push(pick);
    }

    const sorted: DraftPickEntry[] = [];
    for (const roundNum of [...roundMap.keys()].sort((a, b) => a - b)) {
      const roundPicks = roundMap.get(roundNum)!;
      roundPicks.sort((a, b) => {
        const da = a.draft_order ?? 999;
        const db = b.draft_order ?? 999;
        return draftType === "snake" && roundNum % 2 === 0 ? db - da : da - db;
      });
      sorted.push(...roundPicks);
    }

    setLocalPicks(sorted.map((pick, i) => ({ ...pick, pick_number: i + 1 })));
    setHasReorderChanges(true);
  }

  // --- Move pick up/down (works in both filtered and unfiltered views) ---
  function movePick(displayIdx: number, direction: -1 | 1) {
    const target = displayIdx + direction;
    if (target < 0 || target >= displayPicks.length) return;
    const newDisplay = [...displayPicks];
    [newDisplay[displayIdx], newDisplay[target]] = [newDisplay[target], newDisplay[displayIdx]];
    applyReorder(newDisplay);
  }

  // --- Change round number (preseason only) ---
  // Only stores the edit locally; actual reorder happens on "Aplicar rondas"
  function setPickRound(pickId: number, newRound: number) {
    if (isWinter) return;
    setEditedRounds((prev) => ({ ...prev, [pickId]: newRound }));
    setRoundError(null);
    setHasReorderChanges(true);
  }

  // Apply edited rounds: validate and reorder
  function applyRoundEdits() {
    const n = orderedParticipants.length || 1;
    const maxRound = Math.ceil(localPicks.length / n);

    // Merge edited rounds into picks
    const updated = localPicks.map((pick) => {
      const edited = editedRounds[pick.id];
      if (edited !== undefined) {
        const clamped = Math.max(1, Math.min(edited, maxRound));
        return { ...pick, round_number: clamped };
      }
      return pick;
    });

    // Check for rounds with too many picks
    const roundCounts = new Map<number, number>();
    for (const pick of updated) {
      if (filterParticipantId && pick.participant_id !== filterParticipantId) continue;
      roundCounts.set(pick.round_number, (roundCounts.get(pick.round_number) || 0) + 1);
    }

    // When filtering by participant, each round should have exactly 1 pick
    if (filterParticipantId) {
      const duplicateRounds = [...roundCounts.entries()]
        .filter(([, count]) => count > 1)
        .map(([round]) => round);
      if (duplicateRounds.length > 0) {
        setRoundError(`Rondas duplicadas: ${duplicateRounds.map((r) => `R${r}`).join(", ")}. Cada participante debe tener 1 pick por ronda.`);
        return;
      }
    }

    // Sort by round_number, then apply snake/linear order within each round
    const sorted = [...updated].sort((a, b) => a.round_number - b.round_number);
    recalculateGlobal(sorted);
    setEditedRounds({});
    setRoundError(null);
  }

  // --- Drag and drop ---
  function handleDragStart(e: React.DragEvent, displayIdx: number) {
    setDragIndex(displayIdx);
    dragNodeRef.current = e.currentTarget as HTMLDivElement;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(displayIdx));
    requestAnimationFrame(() => {
      if (dragNodeRef.current) {
        dragNodeRef.current.style.opacity = "0.4";
      }
    });
  }

  function handleDragOver(e: React.DragEvent, displayIdx: number) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dragOverIndex !== displayIdx) {
      setDragOverIndex(displayIdx);
    }
  }

  function handleDrop(e: React.DragEvent, targetDisplayIdx: number) {
    e.preventDefault();
    if (dragIndex === null || dragIndex === targetDisplayIdx) {
      resetDrag();
      return;
    }

    const newDisplay = [...displayPicks];
    const [moved] = newDisplay.splice(dragIndex, 1);
    newDisplay.splice(targetDisplayIdx, 0, moved);
    applyReorder(newDisplay);
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
    setEditedRounds({});
    setRoundError(null);
  }

  // Effective target for the manual add: if the participant filter is
  // active, the admin is most likely curating that participant's squad —
  // pre-select them. Otherwise the admin must pick explicitly.
  const effectiveAddTarget = filterParticipantId ?? addTargetParticipantId;

  // Debounced search for the manual add panel.
  const addDraftId = drafts?.drafts.find((d) => d.phase === selectedPhase)?.id;
  useEffect(() => {
    if (!addDraftId) return;
    if (!addSearch.trim() && !addPosFilter && !addTeamFilter) {
      setAddResults([]);
      return;
    }
    const handle = setTimeout(async () => {
      setAddSearching(true);
      try {
        const params = new URLSearchParams();
        if (addSearch.trim()) params.set("q", addSearch.trim());
        if (addPosFilter) params.set("position", addPosFilter);
        if (addTeamFilter) params.set("team_id", addTeamFilter);
        const res = await apiClient.get<PlayerSearchResponse>(
          `/drafts/${addDraftId}/players/search?${params}`,
        );
        setAddResults(res.players.filter((p) => !p.is_already_picked));
      } catch {
        setAddResults([]);
      } finally {
        setAddSearching(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [addSearch, addPosFilter, addTeamFilter, addDraftId]);

  // Derived team list (unique team_names sorted) for the filter dropdown.
  const addTeamOptions = [
    ...new Set([
      ...localPicks.map((p) => p.team_name),
      ...addResults.map((p) => p.team_name),
    ]),
  ].sort();

  async function handleAddPick(player: PlayerSearchItem) {
    if (!addDraftId) return;
    if (!effectiveAddTarget) {
      setError("Selecciona el participante destino antes de añadir el pick");
      return;
    }
    const target = participants.find(
      (p) => p.participant_id === effectiveAddTarget,
    );
    if (
      !window.confirm(
        `¿Añadir ${player.display_name} (${player.position}, ${player.team_name}) a ${target?.display_name ?? "?"}?`,
      )
    ) {
      return;
    }
    setAddingPick(true);
    setError(null);
    try {
      await apiClient.post(`/drafts/${addDraftId}/picks`, {
        player_id: player.id,
        participant_id: effectiveAddTarget,
      });
      await loadDraftDetail();
      setAddSearch("");
      setAddResults([]);
      showSuccess(`Pick añadido: ${player.display_name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al añadir el pick");
    } finally {
      setAddingPick(false);
    }
  }

  async function handleDeletePick(pick: DraftPickEntry) {
    const draftId = drafts?.drafts.find((d) => d.phase === selectedPhase)?.id;
    if (!draftId) return;
    if (
      !window.confirm(
        `¿Eliminar pick #${pick.pick_number} (${pick.player_name} — ${pick.display_name})?`,
      )
    ) {
      return;
    }
    setError(null);
    try {
      await apiClient.delete(`/drafts/${draftId}/picks/${pick.pick_number}`);
      // Backend broadcasts pick_deleted over WS to /drafts/live/{id};
      // here we don't have that subscription, so refetch.
      await loadDraftDetail();
      showSuccess(`Pick #${pick.pick_number} eliminado`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al eliminar el pick");
    }
  }

  function showSuccess(msg: string) {
    setSuccess(msg);
    setTimeout(() => setSuccess(null), 3000);
  }

  if (authLoading || seasonLoading) {
    return <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />;
  }

  if (!user || (!user.isAdmin && !userHasPerm(user.isAdmin, user.permissions, PERM.DRAFT))) {
    return null;
  }

  const currentDraft = drafts?.drafts.find((d) => d.phase === selectedPhase);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">Gestionar Draft</h1>
        <div className="flex items-center gap-2">
          {currentDraft && (
            <Link
              href={`/drafts/live/${currentDraft.id}`}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500"
            >
              Draft en vivo
            </Link>
          )}
          <SeasonSelector />
        </div>
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

      {/* Phase selector — torneos solo tienen pretemporada (sin mercado invernal) */}
      {!isTournamentContext && (
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
      )}

      {/* Step 1: Participant order */}
      {draftDetail && (
        <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
          <h2 className="mb-1 text-lg font-semibold text-vpv-text">
            1. Orden del Draft
          </h2>
          <p className="mb-3 text-xs text-vpv-text-muted">
            Arrastra para reordenar (o usa los botones / teclas como alternativa).
          </p>
          {editableParticipants.length === 0 ? (
            <p className="text-sm text-vpv-text-muted">
              No hay participantes en esta temporada.
            </p>
          ) : (
            <>
              <DraggableParticipantOrder
                participants={editableParticipants}
                allParticipants={participants}
                onReorder={(next) =>
                  setEditableParticipants(
                    next.map((p, i) => ({ ...p, draft_order: i + 1 })),
                  )
                }
                onMove={moveParticipant}
              />
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

      {/* Step 3: Picks */}
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
                {filterParticipantId
                  ? <>{" "}&middot; Arrastra o usa flechas para cambiar ronda{!isWinter && " &middot; Edita la ronda"}</>
                  : <>{" "}&middot; Filtra por participante para reordenar</>
                }
              </p>
            </div>
            {hasReorderChanges && (
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={cancelReorder}
                  className="rounded-lg border border-vpv-border px-4 py-2 text-sm font-medium text-vpv-text-muted transition-colors hover:text-vpv-text"
                >
                  Cancelar
                </button>
                {Object.keys(editedRounds).length > 0 && (
                  <button
                    onClick={applyRoundEdits}
                    className="rounded-lg border border-amber-500 px-4 py-2 text-sm font-medium text-amber-400 transition-colors hover:bg-amber-500/10"
                  >
                    Aplicar rondas
                  </button>
                )}
                <button
                  onClick={saveReorder}
                  disabled={savingReorder || Object.keys(editedRounds).length > 0}
                  className="rounded-lg bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
                >
                  {savingReorder ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            )}
          </div>

          {roundError && (
            <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
              {roundError}
            </div>
          )}

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

          {/* Manual add pick — admin only */}
          <details className="mb-4 rounded-lg border border-vpv-card-border bg-vpv-bg/40 open:bg-vpv-bg">
            <summary className="cursor-pointer select-none px-4 py-2 text-sm font-semibold text-vpv-text">
              + Añadir pick
            </summary>
            <div className="space-y-3 border-t border-vpv-card-border px-4 py-3">
              {/* Target participant: inherits the participant pill when active */}
              {filterParticipantId ? (
                <p className="text-xs text-vpv-text-muted">
                  Asignando a{" "}
                  <span className="font-semibold text-vpv-text">
                    {participants.find(
                      (p) => p.participant_id === filterParticipantId,
                    )?.display_name}
                  </span>
                </p>
              ) : (
                <label className="flex flex-wrap items-center gap-2 text-xs text-vpv-text-muted">
                  Para:
                  <select
                    value={addTargetParticipantId ?? ""}
                    onChange={(e) =>
                      setAddTargetParticipantId(
                        e.target.value ? Number(e.target.value) : null,
                      )
                    }
                    className="rounded border border-vpv-border bg-vpv-card px-2 py-1.5 text-sm text-vpv-text"
                  >
                    <option value="">— elige participante —</option>
                    {orderedParticipants.map((p) => (
                      <option key={p.participant_id} value={p.participant_id}>
                        {p.display_name}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {/* Filters: name + position + team */}
              <div className="flex flex-wrap gap-2">
                <input
                  type="text"
                  value={addSearch}
                  onChange={(e) => setAddSearch(e.target.value)}
                  placeholder="Nombre"
                  className="flex-1 min-w-[160px] rounded border border-vpv-border bg-vpv-card px-2 py-1.5 text-sm text-vpv-text"
                />
                <select
                  value={addPosFilter}
                  onChange={(e) => setAddPosFilter(e.target.value)}
                  className="rounded border border-vpv-border bg-vpv-card px-2 py-1.5 text-sm text-vpv-text"
                >
                  <option value="">Todas pos.</option>
                  <option value="POR">POR</option>
                  <option value="DEF">DEF</option>
                  <option value="MED">MED</option>
                  <option value="DEL">DEL</option>
                </select>
                <select
                  value={addTeamFilter}
                  onChange={(e) => setAddTeamFilter(e.target.value)}
                  className="rounded border border-vpv-border bg-vpv-card px-2 py-1.5 text-sm text-vpv-text"
                >
                  <option value="">Todos equipos</option>
                  {addTeamOptions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
                {(addSearch || addPosFilter || addTeamFilter) && (
                  <button
                    onClick={() => {
                      setAddSearch("");
                      setAddPosFilter("");
                      setAddTeamFilter("");
                      setAddResults([]);
                    }}
                    className="rounded border border-vpv-border px-2 py-1.5 text-xs text-vpv-text-muted hover:text-vpv-text"
                  >
                    Limpiar
                  </button>
                )}
              </div>

              {/* Results */}
              <div className="space-y-1">
                {addSearching && (
                  <p className="py-2 text-center text-xs text-vpv-text-muted">
                    Buscando…
                  </p>
                )}
                {!addSearching &&
                  !addSearch &&
                  !addPosFilter &&
                  !addTeamFilter && (
                    <p className="py-2 text-center text-xs text-vpv-text-muted/70">
                      Escribe un nombre o usa los filtros para buscar
                    </p>
                  )}
                {!addSearching &&
                  (addSearch || addPosFilter || addTeamFilter) &&
                  addResults.length === 0 && (
                    <p className="py-2 text-center text-xs text-vpv-text-muted/70">
                      Sin resultados disponibles
                    </p>
                  )}
                {addResults.slice(0, 20).map((player) => (
                  <button
                    key={player.id}
                    onClick={() => handleAddPick(player)}
                    disabled={addingPick || !effectiveAddTarget}
                    className="flex w-full items-center gap-2 rounded border border-transparent bg-vpv-card px-2 py-1.5 text-left text-sm text-vpv-text transition-colors hover:border-vpv-accent disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <PlayerAvatar
                      photoPath={player.photo_path}
                      name={player.display_name}
                      size={24}
                    />
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${POS_COLORS[player.position] ?? ""}`}>
                      {player.position}
                    </span>
                    <span className="flex-1 truncate font-medium">
                      {player.display_name}
                    </span>
                    <span className="text-xs text-vpv-text-muted">
                      {player.team_name}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </details>

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
                // Separator: preseason = by round, winter = by participant
                const isFirstOfGroup = isWinter
                  ? displayIdx === 0 ||
                    displayPicks[displayIdx - 1].participant_id !== pick.participant_id
                  : displayIdx === 0 ||
                    displayPicks[displayIdx - 1].round_number !== pick.round_number;

                const isDragOver = dragOverIndex === displayIdx;
                const colors = getColorForParticipant(pick.participant_id, participants);

                // For preseason filtered view: show sequential "round" within participant
                const filteredRound = filterParticipantId ? displayIdx + 1 : pick.round_number;

                return (
                  <div key={pick.id}>
                    {isFirstOfGroup && !filterParticipantId && (
                      <div className="pb-1 pt-4 first:pt-0">
                        <span className={`text-xs font-semibold uppercase tracking-wider ${isWinter ? colors.text : "text-vpv-text-muted"}`}>
                          {isWinter ? pick.display_name : `Ronda ${pick.round_number}`}
                        </span>
                      </div>
                    )}
                    <div
                      draggable={!!filterParticipantId}
                      onDragStart={filterParticipantId ? (e) => handleDragStart(e, displayIdx) : undefined}
                      onDragOver={filterParticipantId ? (e) => handleDragOver(e, displayIdx) : undefined}
                      onDrop={filterParticipantId ? (e) => handleDrop(e, displayIdx) : undefined}
                      onDragEnd={filterParticipantId ? handleDragEnd : undefined}
                      className={`group flex items-center gap-2 rounded-lg border-l-4 px-3 py-2.5 text-sm transition-all sm:gap-3 ${colors.border} ${
                        isDragOver
                          ? "bg-vpv-accent/10 ring-2 ring-vpv-accent/40"
                          : "bg-vpv-bg hover:bg-vpv-bg/80"
                      }${filterParticipantId ? " cursor-grab active:cursor-grabbing" : ""}`}
                    >
                      {/* Grip handle + arrows: only when filtering by participant */}
                      {filterParticipantId && (
                        <>
                          <span className="hidden flex-shrink-0 text-vpv-text-muted/40 group-hover:text-vpv-text-muted sm:block">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
                              <path fillRule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm0 5.5a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75zm.75 4.75a.75.75 0 000 1.5h14.5a.75.75 0 000-1.5H2.75z" clipRule="evenodd" />
                            </svg>
                          </span>
                        </>
                      )}

                      {/* Pick number */}
                      <span className="w-7 flex-shrink-0 text-center text-xs font-bold text-vpv-accent">
                        #{pick.pick_number}
                      </span>

                      {/* Move arrows: only when filtering */}
                      {filterParticipantId && (
                        <div className="flex flex-shrink-0 flex-col gap-0.5">
                          <button
                            onClick={(e) => { e.stopPropagation(); movePick(displayIdx, -1); }}
                            disabled={displayIdx === 0}
                            className="rounded p-0.5 text-vpv-text-muted hover:bg-vpv-card hover:text-vpv-text disabled:opacity-20"
                            title="Subir pick"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                              <path fillRule="evenodd" d="M11.78 9.78a.75.75 0 0 1-1.06 0L8 7.06 5.28 9.78a.75.75 0 0 1-1.06-1.06l3.25-3.25a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06Z" clipRule="evenodd" />
                            </svg>
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); movePick(displayIdx, 1); }}
                            disabled={displayIdx === displayPicks.length - 1}
                            className="rounded p-0.5 text-vpv-text-muted hover:bg-vpv-card hover:text-vpv-text disabled:opacity-20"
                            title="Bajar pick"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                              <path fillRule="evenodd" d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                            </svg>
                          </button>
                        </div>
                      )}

                      {/* Player photo */}
                      <PlayerAvatar photoPath={pick.photo_path} name={pick.player_name} size={28} />

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

                      {/* Participant badge (always show when not filtering in winter, since grouped by participant) */}
                      {(!isWinter || filterParticipantId) && (
                        <span className={`flex-shrink-0 truncate rounded-full px-2 py-0.5 text-[10px] font-medium ${colors.bg} ${colors.text}`}>
                          {pick.display_name}
                        </span>
                      )}

                      {/* Delete pick (admin only — page already gates non-admins) */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeletePick(pick);
                        }}
                        title={`Eliminar pick #${pick.pick_number}`}
                        aria-label={`Eliminar pick #${pick.pick_number}`}
                        className="ml-1 inline-flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-vpv-text-muted opacity-0 transition-all hover:bg-red-500/15 hover:text-red-500 group-hover:opacity-100"
                      >
                        ✕
                      </button>

                      {/* Round: editable in preseason when filtering, read-only otherwise */}
                      {!isWinter && (
                        filterParticipantId ? (
                          <div className="flex flex-shrink-0 items-center gap-0.5">
                            <span className="text-[10px] text-vpv-text-muted">R</span>
                            <input
                              type="number"
                              min={1}
                              max={displayPicks.length}
                              value={editedRounds[pick.id] ?? filteredRound}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => {
                                const val = parseInt(e.target.value);
                                if (!isNaN(val) && val >= 1) {
                                  setPickRound(pick.id, val);
                                }
                              }}
                              className={`w-10 rounded border px-1 py-0.5 text-center text-xs text-vpv-text ${
                                editedRounds[pick.id] !== undefined
                                  ? "border-vpv-accent bg-vpv-accent/10"
                                  : "border-vpv-border bg-vpv-card"
                              }`}
                            />
                          </div>
                        ) : (
                          <span className="w-8 flex-shrink-0 text-center text-[10px] text-vpv-text-muted">
                            R{pick.round_number}
                          </span>
                        )
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
      <h2 className="mb-1 text-lg font-semibold text-vpv-text">
        1. Orden del Draft
      </h2>
      <p className="mb-3 text-xs text-vpv-text-muted">
        Arrastra para reordenar (o usa los botones / teclas como alternativa).
      </p>
      {error && (
        <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">{error}</div>
      )}
      {success && (
        <div className="mb-3 rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-2 text-sm text-green-400">{success}</div>
      )}
      <DraggableParticipantOrder
        participants={participants}
        allParticipants={participants}
        onReorder={(next) =>
          setParticipants(next.map((p, i) => ({ ...p, draft_order: i + 1 })))
        }
        onMove={moveParticipant}
      />
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

/** Sortable participant list shared by both Step 1 sections.
 *  Drag to reorder; arrow buttons remain as accessible fallback.
 */
function DraggableParticipantOrder({
  participants,
  allParticipants,
  onReorder,
  onMove,
}: {
  participants: DraftParticipant[];
  allParticipants: DraftParticipant[];
  onReorder: (next: DraftParticipant[]) => void;
  onMove: (index: number, direction: -1 | 1) => void;
}) {
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = participants.findIndex((p) => String(p.participant_id) === String(active.id));
    const newIdx = participants.findIndex((p) => String(p.participant_id) === String(over.id));
    if (oldIdx === -1 || newIdx === -1) return;
    onReorder(arrayMove(participants, oldIdx, newIdx));
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext
        items={participants.map((p) => String(p.participant_id))}
        strategy={verticalListSortingStrategy}
      >
        <ul className="space-y-1">
          {participants.map((p, i) => (
            <SortableParticipantItem
              key={p.participant_id}
              participant={p}
              index={i}
              total={participants.length}
              colorBorder={getColorForParticipant(p.participant_id, allParticipants).border}
              onMoveUp={() => onMove(i, -1)}
              onMoveDown={() => onMove(i, 1)}
            />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  );
}

function SortableParticipantItem({
  participant,
  index,
  total,
  colorBorder,
  onMoveUp,
  onMoveDown,
}: {
  participant: DraftParticipant;
  index: number;
  total: number;
  colorBorder: string;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: String(participant.participant_id) });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
    touchAction: "none",
  };
  return (
    <li
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 rounded-lg border-l-4 bg-vpv-bg px-4 py-2 ${colorBorder} ${
        isDragging ? "" : "hover:bg-vpv-bg/80"
      }`}
    >
      <span
        {...attributes}
        {...listeners}
        className="cursor-grab text-vpv-text-muted/60 active:cursor-grabbing select-none"
        aria-label="Arrastra para reordenar"
        title="Arrastra para reordenar"
      >
        ⋮⋮
      </span>
      <span className="w-8 text-center text-sm font-bold text-vpv-accent">
        {participant.draft_order ?? index + 1}
      </span>
      <span className="flex-1 text-sm text-vpv-text">{participant.display_name}</span>
      <button
        onClick={onMoveUp}
        disabled={index === 0}
        className="rounded p-1 text-vpv-text-muted hover:text-vpv-text disabled:opacity-30"
        title="Subir"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
          <path fillRule="evenodd" d="M14.77 12.79a.75.75 0 01-1.06-.02L10 8.832 6.29 12.77a.75.75 0 11-1.08-1.04l4.25-4.5a.75.75 0 011.08 0l4.25 4.5a.75.75 0 01-.02 1.06z" clipRule="evenodd" />
        </svg>
      </button>
      <button
        onClick={onMoveDown}
        disabled={index === total - 1}
        className="rounded p-1 text-vpv-text-muted hover:text-vpv-text disabled:opacity-30"
        title="Bajar"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
        </svg>
      </button>
    </li>
  );
}
