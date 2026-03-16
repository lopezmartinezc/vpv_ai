"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { apiClient } from "@/lib/api-client";
import { SeasonSelector } from "@/components/layout/season-selector";
import type {
  AddPickResponse,
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

export default function GestionarDraftPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason, loading: seasonLoading } = useSeason();

  // State
  const [drafts, setDrafts] = useState<DraftListResponse | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<string>("preseason");
  const [draftDetail, setDraftDetail] = useState<DraftDetailResponse | null>(null);
  const [participants, setParticipants] = useState<DraftParticipant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Player search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchPosition, setSearchPosition] = useState<string>("");
  const [searchResults, setSearchResults] = useState<PlayerSearchItem[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout>>(null);

  // Pick assignment
  const [selectedParticipantId, setSelectedParticipantId] = useState<number | null>(null);

  // Auth guard
  useEffect(() => {
    if (!authLoading && user && !user.isAdmin && !user.isDraftManager) {
      router.push("/");
    }
  }, [user, authLoading, router]);

  // Load drafts when season changes
  const loadDrafts = useCallback(async () => {
    if (!selectedSeason) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<DraftListResponse>(
        `/drafts/${selectedSeason.id}`,
      );
      setDrafts(data);
      // Also load participants
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

  async function loadParticipants(seasonId: number): Promise<DraftParticipant[]> {
    // Get participants from any existing draft detail, or from the draft list endpoint
    try {
      // Try to get detail of any phase to get participants
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

  // Load draft detail when phase changes
  useEffect(() => {
    if (!selectedSeason || !drafts) return;
    const draft = drafts.drafts.find((d) => d.phase === selectedPhase);
    if (!draft) {
      setDraftDetail(null);
      return;
    }
    apiClient
      .get<DraftDetailResponse>(`/drafts/${selectedSeason.id}/${selectedPhase}`)
      .then(setDraftDetail)
      .catch(() => setDraftDetail(null));
  }, [selectedSeason, drafts, selectedPhase]);

  // --- Participant order ---
  function moveParticipant(index: number, direction: -1 | 1) {
    const newList = [...participants];
    const target = index + direction;
    if (target < 0 || target >= newList.length) return;
    [newList[index], newList[target]] = [newList[target], newList[index]];
    // Reassign draft_order
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
      setSuccess("Orden guardado");
      setTimeout(() => setSuccess(null), 3000);
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
      setSuccess(`Draft ${PHASE_LABELS[phase]} creado`);
      setTimeout(() => setSuccess(null), 3000);
      await loadDrafts();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando draft");
    } finally {
      setLoading(false);
    }
  }

  // --- Player search ---
  function handleSearchChange(q: string) {
    setSearchQuery(q);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    if (!draftDetail || q.length < 2) {
      setSearchResults([]);
      return;
    }
    searchTimeout.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const draftId = drafts?.drafts.find((d) => d.phase === selectedPhase)?.id;
        if (!draftId) return;
        const posParam = searchPosition ? `&position=${searchPosition}` : "";
        const data = await apiClient.get<PlayerSearchResponse>(
          `/drafts/${draftId}/players/search?q=${encodeURIComponent(q)}${posParam}`,
        );
        setSearchResults(data.players);
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);
  }

  // --- Add pick ---
  async function addPick(playerId: number) {
    if (!selectedParticipantId) {
      setError("Selecciona un participante primero");
      return;
    }
    const draftId = drafts?.drafts.find((d) => d.phase === selectedPhase)?.id;
    if (!draftId) return;
    setError(null);
    try {
      const pick = await apiClient.post<AddPickResponse>(
        `/drafts/${draftId}/picks`,
        { participant_id: selectedParticipantId, player_id: playerId },
      );
      setSuccess(`Pick #${pick.pick_number}: ${pick.player_name} -> ${pick.display_name}`);
      setTimeout(() => setSuccess(null), 3000);
      setSearchQuery("");
      setSearchResults([]);
      // Reload detail
      if (selectedSeason) {
        const detail = await apiClient.get<DraftDetailResponse>(
          `/drafts/${selectedSeason.id}/${selectedPhase}`,
        );
        setDraftDetail(detail);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error añadiendo pick");
    }
  }

  // --- Delete pick ---
  async function deletePick(pickNumber: number) {
    const draftId = drafts?.drafts.find((d) => d.phase === selectedPhase)?.id;
    if (!draftId) return;
    setError(null);
    try {
      await apiClient.delete(`/drafts/${draftId}/picks/${pickNumber}`);
      setSuccess(`Pick #${pickNumber} eliminado`);
      setTimeout(() => setSuccess(null), 3000);
      if (selectedSeason) {
        const detail = await apiClient.get<DraftDetailResponse>(
          `/drafts/${selectedSeason.id}/${selectedPhase}`,
        );
        setDraftDetail(detail);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error eliminando pick");
    }
  }

  if (authLoading || seasonLoading) {
    return <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />;
  }

  if (!user || (!user.isAdmin && !user.isDraftManager)) {
    return null;
  }

  const currentDraft = drafts?.drafts.find((d) => d.phase === selectedPhase);

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
                  className="flex items-center gap-3 rounded-lg bg-vpv-bg px-4 py-2"
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

      {/* Step 3: Pick registration */}
      {currentDraft && (
        <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
          <h2 className="mb-1 text-lg font-semibold text-vpv-text">
            3. Registrar Picks
          </h2>
          <p className="mb-4 text-xs text-vpv-text-muted">
            {PHASE_LABELS[selectedPhase]} &middot;{" "}
            {TYPE_LABELS[currentDraft.draft_type]} &middot;{" "}
            {draftDetail?.picks.length ?? 0} picks registrados
          </p>

          {/* Participant selector */}
          <div className="mb-4">
            <label className="mb-1 block text-xs font-medium text-vpv-text-muted">
              Participante
            </label>
            <select
              value={selectedParticipantId ?? ""}
              onChange={(e) =>
                setSelectedParticipantId(
                  e.target.value ? Number(e.target.value) : null,
                )
              }
              className="w-full rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text"
            >
              <option value="">Selecciona participante...</option>
              {participants.map((p) => (
                <option key={p.participant_id} value={p.participant_id}>
                  {p.draft_order ? `#${p.draft_order} ` : ""}
                  {p.display_name}
                </option>
              ))}
            </select>
          </div>

          {/* Player search */}
          <div className="mb-4 flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                placeholder="Buscar jugador..."
                className="w-full rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text placeholder:text-vpv-text-muted"
              />
              {searchLoading && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
                </div>
              )}
            </div>
            <select
              value={searchPosition}
              onChange={(e) => {
                setSearchPosition(e.target.value);
                if (searchQuery.length >= 2) handleSearchChange(searchQuery);
              }}
              className="rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text"
            >
              <option value="">Pos.</option>
              <option value="POR">POR</option>
              <option value="DEF">DEF</option>
              <option value="MED">MED</option>
              <option value="DEL">DEL</option>
            </select>
          </div>

          {/* Search results */}
          {searchResults.length > 0 && (
            <div className="mb-4 max-h-60 overflow-y-auto rounded-lg border border-vpv-border">
              {searchResults.map((player) => (
                <button
                  key={player.id}
                  onClick={() => !player.is_already_picked && addPick(player.id)}
                  disabled={player.is_already_picked}
                  className={`flex w-full items-center gap-3 border-b border-vpv-border px-4 py-2.5 text-left text-sm transition-colors last:border-b-0 ${
                    player.is_already_picked
                      ? "cursor-not-allowed opacity-40"
                      : "hover:bg-vpv-bg"
                  }`}
                >
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs font-medium ${POS_COLORS[player.position] ?? ""}`}
                  >
                    {player.position}
                  </span>
                  <span className="flex-1 text-vpv-text">
                    {player.display_name}
                  </span>
                  <span className="text-xs text-vpv-text-muted">
                    {player.team_name}
                  </span>
                  {player.is_already_picked && (
                    <span className="text-xs text-red-400">Elegido</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Picks table */}
          <PicksTable
            picks={draftDetail?.picks ?? []}
            onDelete={deletePick}
          />
        </section>
      )}
    </div>
  );
}

function PicksTable({
  picks,
  onDelete,
}: {
  picks: DraftPickEntry[];
  onDelete: (pickNumber: number) => void;
}) {
  if (picks.length === 0) {
    return (
      <p className="text-sm text-vpv-text-muted">
        No hay picks registrados todavia.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-vpv-border text-left text-xs text-vpv-text-muted">
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Ronda</th>
            <th className="px-3 py-2">Participante</th>
            <th className="px-3 py-2">Jugador</th>
            <th className="px-3 py-2">Pos</th>
            <th className="px-3 py-2">Equipo</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {picks.map((pick) => (
            <tr
              key={pick.pick_number}
              className="border-b border-vpv-border/50 text-vpv-text"
            >
              <td className="px-3 py-2 font-medium text-vpv-accent">
                {pick.pick_number}
              </td>
              <td className="px-3 py-2 text-vpv-text-muted">
                R{pick.round_number}
              </td>
              <td className="px-3 py-2">{pick.display_name}</td>
              <td className="px-3 py-2 font-medium">{pick.player_name}</td>
              <td className="px-3 py-2">
                <span
                  className={`rounded px-1.5 py-0.5 text-xs font-medium ${POS_COLORS[pick.position] ?? ""}`}
                >
                  {pick.position}
                </span>
              </td>
              <td className="px-3 py-2 text-vpv-text-muted">
                {pick.team_name}
              </td>
              <td className="px-3 py-2">
                <button
                  onClick={() => onDelete(pick.pick_number)}
                  className="rounded p-1 text-red-400/60 transition-colors hover:text-red-400"
                  title="Eliminar pick"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                    <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022 1.005 11.07A2.75 2.75 0 007.768 19.5h4.464a2.75 2.75 0 002.748-2.479l1.005-11.07.15.022a.75.75 0 10.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 01.7.797l-.5 5.5a.75.75 0 01-1.495-.137l.5-5.5a.75.75 0 01.796-.66zm2.84 0a.75.75 0 01.795.66l.5 5.5a.75.75 0 01-1.495.137l-.5-5.5a.75.75 0 01.7-.797z" clipRule="evenodd" />
                  </svg>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
