"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SeasonDetail {
  id: number;
  name: string;
  status: string;
  matchday_current: number;
}

interface LineupPlayer {
  player_id: number;
  display_name: string;
  position_slot: string;
  display_order: number;
  points: number;
  photo_path: string | null;
}

interface ParticipantLineup {
  participant_id: number;
  display_name: string;
  has_lineup: boolean;
  formation: string | null;
  total_points: number;
  confirmed_at: string | null;
  players: LineupPlayer[];
}

interface LineupsResponse {
  season_id: number;
  matchday_number: number;
  participants: ParticipantLineup[];
}

interface SquadPlayer {
  player_id: number;
  display_name: string;
  /** "POR" | "DEF" | "MED" | "DEL" */
  position: string;
  team_name: string;
  photo_path: string | null;
  points_this_matchday: number;
}

interface SquadResponse {
  participant_id: number;
  display_name: string;
  squad: SquadPlayer[];
}

interface SaveResult {
  lineup_id: number;
  formation: string;
  old_total_points: number;
  new_total_points: number;
  delta: number;
  players: { player_id: number; display_name: string; position_slot: string; points: number }[];
  rankings_updated: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const VALID_FORMATIONS = [
  "1-3-4-3",
  "1-3-5-2",
  "1-4-3-3",
  "1-4-4-2",
  "1-4-5-1",
  "1-5-3-2",
  "1-5-4-1",
] as const;

type Formation = (typeof VALID_FORMATIONS)[number];

/** Parse "1-4-3-3" → { POR: 1, DEF: 4, MED: 3, DEL: 3 } */
function parseFormation(f: string): { POR: number; DEF: number; MED: number; DEL: number } {
  const parts = f.split("-").map(Number);
  return { POR: parts[0] ?? 1, DEF: parts[1] ?? 4, MED: parts[2] ?? 3, DEL: parts[3] ?? 3 };
}

/** Build ordered list of position slots for a formation, e.g. ["POR-1","DEF-1",...] */
function buildSlots(formation: string): { slot: string; pos: string }[] {
  const counts = parseFormation(formation);
  const result: { slot: string; pos: string }[] = [];
  const positions: Array<keyof typeof counts> = ["POR", "DEF", "MED", "DEL"];
  for (const pos of positions) {
    for (let i = 1; i <= counts[pos]; i++) {
      result.push({ slot: `${pos}-${i}`, pos });
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Inline editor component
// ---------------------------------------------------------------------------

interface EditorProps {
  participant: ParticipantLineup;
  seasonId: number;
  matchdayNumber: number;
  onSave: (participantId: number, result: SaveResult) => void;
  onCancel: () => void;
}

function LineupEditor({ participant, seasonId, matchdayNumber, onSave, onCancel }: EditorProps) {
  const [formation, setFormation] = useState<string>(
    participant.formation ?? "1-4-3-3",
  );
  /** slot → player_id (string for select value, "" = empty) */
  const [slotMap, setSlotMap] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const p of participant.players) {
      initial[p.position_slot] = String(p.player_id);
    }
    return initial;
  });
  const [squad, setSquad] = useState<SquadPlayer[]>([]);
  const [squadLoading, setSquadLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load squad on mount
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setSquadLoading(true);
      try {
        const data = await apiClient.get<SquadResponse>(
          `/lineups/admin/${seasonId}/${matchdayNumber}/${participant.participant_id}/squad`,
        );
        if (!cancelled) setSquad(data.squad);
      } catch {
        if (!cancelled) setError("Error al cargar el plantel");
      } finally {
        if (!cancelled) setSquadLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [seasonId, matchdayNumber, participant.participant_id]);

  function handleFormationChange(newFormation: string) {
    setFormation(newFormation);
    // Reset all slots when formation changes
    setSlotMap({});
  }

  function handleSlotChange(slot: string, playerId: string) {
    setSlotMap((prev) => {
      const next = { ...prev };
      // Unassign the player from any other slot to avoid duplicates
      if (playerId !== "") {
        for (const s of Object.keys(next)) {
          if (next[s] === playerId && s !== slot) {
            next[s] = "";
          }
        }
      }
      next[slot] = playerId;
      return next;
    });
  }

  async function handleSave() {
    const slots = buildSlots(formation);
    const players: { player_id: number; position_slot: string }[] = [];
    for (const { slot } of slots) {
      const pid = slotMap[slot];
      if (!pid) {
        setError("Debes asignar un jugador a cada posicion");
        return;
      }
      players.push({ player_id: Number(pid), position_slot: slot });
    }
    setSaving(true);
    setError(null);
    try {
      const result = await apiClient.put<SaveResult>(
        `/lineups/admin/${seasonId}/${matchdayNumber}/${participant.participant_id}`,
        { formation, players },
      );
      onSave(participant.participant_id, result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  const slots = buildSlots(formation);

  // Group slots by position for display
  const positionGroups: Record<string, { slot: string; pos: string }[]> = {};
  for (const s of slots) {
    if (!positionGroups[s.pos]) positionGroups[s.pos] = [];
    positionGroups[s.pos].push(s);
  }

  // Players by position for dropdowns
  const byPosition: Record<string, SquadPlayer[]> = {};
  for (const p of squad) {
    if (!byPosition[p.position]) byPosition[p.position] = [];
    byPosition[p.position].push(p);
  }

  const positionLabels: Record<string, string> = {
    POR: "Portero",
    DEF: "Defensas",
    MED: "Mediocampistas",
    DEL: "Delanteros",
  };

  const positionOrder = ["POR", "DEF", "MED", "DEL"] as const;

  if (squadLoading) {
    return (
      <div className="mt-2 space-y-2 rounded-lg border border-vpv-border bg-vpv-bg p-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-8 animate-pulse rounded bg-vpv-border" />
        ))}
      </div>
    );
  }

  return (
    <div className="mt-2 rounded-lg border border-vpv-accent/40 bg-vpv-bg p-4">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium text-vpv-text">Formacion:</label>
        <select
          value={formation}
          onChange={(e) => handleFormationChange(e.target.value)}
          className="rounded border border-vpv-border bg-vpv-card px-3 py-1.5 text-sm text-vpv-text"
        >
          {VALID_FORMATIONS.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-4">
        {positionOrder.map((pos) => {
          const posSlots = positionGroups[pos];
          if (!posSlots || posSlots.length === 0) return null;
          const candidates = byPosition[pos] ?? [];

          return (
            <div key={pos}>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
                {positionLabels[pos]} ({posSlots.length})
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {posSlots.map(({ slot }) => (
                  <div key={slot} className="flex items-center gap-2">
                    <span className="w-14 rounded bg-vpv-border px-1.5 py-0.5 text-center text-xs text-vpv-text-muted">
                      {slot}
                    </span>
                    <select
                      value={slotMap[slot] ?? ""}
                      onChange={(e) => handleSlotChange(slot, e.target.value)}
                      className="flex-1 rounded border border-vpv-border bg-vpv-card px-2 py-1.5 text-sm text-vpv-text"
                      aria-label={`Jugador para ${slot}`}
                    >
                      <option value="">-- Elige jugador --</option>
                      {candidates.map((p) => (
                        <option key={p.player_id} value={String(p.player_id)}>
                          {p.display_name} ({p.team_name}) — {p.points_this_matchday} pts
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {error && (
        <p className="mt-3 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      <div className="mt-4 flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Guardando..." : "Guardar"}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          className="rounded border border-vpv-border px-4 py-2 text-sm font-medium text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Participant card
// ---------------------------------------------------------------------------

interface CardProps {
  participant: ParticipantLineup;
  isEditing: boolean;
  seasonId: number;
  matchdayNumber: number;
  onEditOpen: (id: number) => void;
  onSave: (participantId: number, result: SaveResult) => void;
  onCancel: () => void;
}

function ParticipantCard({
  participant,
  isEditing,
  seasonId,
  matchdayNumber,
  onEditOpen,
  onSave,
  onCancel,
}: CardProps) {
  const positionOrder = ["POR", "DEF", "MED", "DEL"] as const;
  const positionLabels: Record<string, string> = {
    POR: "POR",
    DEF: "DEF",
    MED: "MED",
    DEL: "DEL",
  };

  /** Group lineup players by position extracted from position_slot ("DEF-2" → "DEF") */
  const byPosition: Record<string, LineupPlayer[]> = {};
  for (const p of participant.players) {
    const pos = p.position_slot.split("-")[0];
    if (!byPosition[pos]) byPosition[pos] = [];
    byPosition[pos].push(p);
  }
  // Sort each group by display_order
  for (const pos of Object.keys(byPosition)) {
    byPosition[pos].sort((a, b) => a.display_order - b.display_order);
  }

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      {/* Card header */}
      <div className="flex flex-wrap items-center gap-3 border-b border-vpv-border px-4 py-3">
        <span className="flex-1 font-semibold text-vpv-text">
          {participant.display_name}
        </span>
        {participant.has_lineup ? (
          <>
            {participant.formation && (
              <span className="rounded bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                {participant.formation}
              </span>
            )}
            <span className="rounded bg-vpv-bg px-2 py-0.5 text-xs text-vpv-text-muted">
              {participant.total_points} pts
            </span>
          </>
        ) : (
          <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">
            Sin alineacion
          </span>
        )}
        <button
          onClick={() => onEditOpen(participant.participant_id)}
          className="rounded border border-vpv-border px-3 py-1 text-xs font-medium text-vpv-text-muted transition-colors hover:border-vpv-accent hover:text-vpv-accent"
          aria-expanded={isEditing}
        >
          {isEditing ? "Cerrando..." : participant.has_lineup ? "Editar" : "Crear"}
        </button>
      </div>

      {/* Players grouped by position */}
      {participant.has_lineup && participant.players.length > 0 && (
        <div className="divide-y divide-vpv-border/40 px-4 py-2">
          {positionOrder.map((pos) => {
            const group = byPosition[pos];
            if (!group || group.length === 0) return null;
            return (
              <div key={pos} className="flex flex-wrap gap-x-4 gap-y-0.5 py-1.5">
                <span className="w-8 shrink-0 text-xs font-semibold text-vpv-text-muted">
                  {positionLabels[pos]}
                </span>
                <div className="flex flex-wrap gap-x-4 gap-y-0.5">
                  {group.map((p) => (
                    <span key={p.player_id} className="text-sm text-vpv-text">
                      {p.display_name}
                      <span className="ml-1 text-xs text-vpv-text-muted">
                        ({p.points})
                      </span>
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Inline editor */}
      {isEditing && (
        <div className="px-4 pb-4">
          <LineupEditor
            participant={participant}
            seasonId={seasonId}
            matchdayNumber={matchdayNumber}
            onSave={onSave}
            onCancel={onCancel}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminAlineacionesPage() {
  const [seasons, setSeasons] = useState<SeasonDetail[]>([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);
  const [matchdayInput, setMatchdayInput] = useState<string>("");
  const [searchedMatchday, setSearchedMatchday] = useState<number | null>(null);
  const [lineups, setLineups] = useState<ParticipantLineup[]>([]);
  const [loading, setLoading] = useState(true);
  const [lineupsLoading, setLineupsLoading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const selectedSeason = seasons.find((s) => s.id === selectedSeasonId) ?? null;

  // Load seasons on mount
  useEffect(() => {
    async function fetchSeasons() {
      try {
        const data = await apiClient.get<SeasonDetail[]>("/seasons");
        setSeasons(data);
        if (data.length > 0) {
          const active = data.find((s) => s.status === "active") ?? data[0];
          setSelectedSeasonId(active.id);
          setMatchdayInput(String(active.matchday_current));
        }
      } catch {
        // handled by auth context
      } finally {
        setLoading(false);
      }
    }
    fetchSeasons();
  }, []);

  // When season changes, reset matchday input to that season's current matchday
  useEffect(() => {
    if (selectedSeason) {
      setMatchdayInput(String(selectedSeason.matchday_current));
      setSearchedMatchday(null);
      setLineups([]);
      setEditingId(null);
    }
  }, [selectedSeason]);

  const fetchLineups = useCallback(async (seasonId: number, matchday: number) => {
    setLineupsLoading(true);
    setEditingId(null);
    try {
      const data = await apiClient.get<LineupsResponse>(
        `/lineups/admin/${seasonId}/${matchday}/all`,
      );
      const sorted = [...data.participants].sort((a, b) =>
        a.display_name.localeCompare(b.display_name),
      );
      setLineups(sorted);
    } catch {
      setLineups([]);
    } finally {
      setLineupsLoading(false);
    }
  }, []);

  function handleSearch() {
    const n = parseInt(matchdayInput, 10);
    if (!selectedSeasonId || isNaN(n) || n < 1) return;
    setSearchedMatchday(n);
    fetchLineups(selectedSeasonId, n);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSearch();
  }

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  }

  function handleSave(participantId: number, result: SaveResult) {
    // Update lineup in state
    setLineups((prev) =>
      prev.map((p) => {
        if (p.participant_id !== participantId) return p;
        return {
          ...p,
          has_lineup: true,
          formation: result.formation,
          total_points: result.new_total_points,
          players: result.players.map((rp, i) => ({
            player_id: rp.player_id,
            display_name: rp.display_name,
            position_slot: rp.position_slot,
            display_order: i,
            points: rp.points,
            photo_path: null,
          })),
        };
      }),
    );
    setEditingId(null);

    const sign = result.delta >= 0 ? "+" : "";
    showToast(
      `Puntos: ${result.old_total_points} \u2192 ${result.new_total_points} (${sign}${result.delta})`,
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-lg bg-vpv-border" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toast */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-6 right-6 z-50 rounded-lg border border-green-500/40 bg-vpv-card px-5 py-3 text-sm font-medium text-green-400 shadow-lg"
        >
          {toast}
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-vpv-text-muted">Temporada</label>
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
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-vpv-text-muted">Jornada</label>
          <input
            type="number"
            min={1}
            value={matchdayInput}
            onChange={(e) => setMatchdayInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-24 rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text"
            aria-label="Numero de jornada"
          />
        </div>

        <button
          onClick={handleSearch}
          disabled={!selectedSeasonId || !matchdayInput || lineupsLoading}
          className="rounded bg-vpv-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {lineupsLoading ? "Cargando..." : "Buscar"}
        </button>

        {searchedMatchday !== null && selectedSeason && (
          <span className="text-xs text-vpv-text-muted">
            {selectedSeason.name} — J{searchedMatchday}
          </span>
        )}
      </div>

      {/* Empty state before first search */}
      {searchedMatchday === null && !lineupsLoading && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-10 text-center text-sm text-vpv-text-muted">
          Selecciona una temporada y jornada y pulsa Buscar
        </div>
      )}

      {/* Loading skeleton */}
      {lineupsLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-lg bg-vpv-border" />
          ))}
        </div>
      )}

      {/* Lineup cards */}
      {!lineupsLoading && searchedMatchday !== null && (
        <div className="space-y-3">
          {lineups.length === 0 && (
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-10 text-center text-sm text-vpv-text-muted">
              No hay participantes para esta jornada
            </div>
          )}

          {lineups.map((participant) => (
            <ParticipantCard
              key={participant.participant_id}
              participant={participant}
              isEditing={editingId === participant.participant_id}
              seasonId={selectedSeasonId!}
              matchdayNumber={searchedMatchday}
              onEditOpen={(id) => setEditingId((prev) => (prev === id ? null : id))}
              onSave={handleSave}
              onCancel={() => setEditingId(null)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
