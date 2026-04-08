"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { PitchView } from "@/components/ui/pitch-view";
import type { PitchPlayer } from "@/components/ui/pitch-view";
import { PlayerAvatar } from "@/components/ui/player-avatar";

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
  position: string;
  team_name: string;
  photo_path: string | null;
  points_this_matchday: number | null;
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
  players: {
    player_id: number;
    display_name: string;
    position_slot: string;
    points: number;
  }[];
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

const POSITIONS = ["POR", "DEF", "MED", "DEL"] as const;

const POS_COLORS: Record<string, string> = {
  POR: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  DEF: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  MED: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  DEL: "bg-rose-500/15 text-rose-400 border-rose-500/30",
};

function parseFormation(f: string): Record<string, number> {
  const parts = f.split("-").map(Number);
  return { POR: parts[0] ?? 1, DEF: parts[1] ?? 4, MED: parts[2] ?? 3, DEL: parts[3] ?? 3 };
}

// ---------------------------------------------------------------------------
// Visual editor with pitch + squad sidebar
// ---------------------------------------------------------------------------

interface EditorProps {
  participant: ParticipantLineup;
  seasonId: number;
  matchdayNumber: number;
  onSave: (participantId: number, result: SaveResult) => void;
  onCancel: () => void;
}

function LineupEditor({ participant, seasonId, matchdayNumber, onSave, onCancel }: EditorProps) {
  const [formation, setFormation] = useState<string>(participant.formation ?? "1-4-3-3");
  const [selectedPlayers, setSelectedPlayers] = useState<
    { player_id: number; display_name: string; position_slot: string; photo_path: string | null }[]
  >(() =>
    participant.players.map((p) => ({
      player_id: p.player_id,
      display_name: p.display_name,
      position_slot: p.position_slot.split("-")[0],
      photo_path: p.photo_path,
    })),
  );
  const [squad, setSquad] = useState<SquadPlayer[]>([]);
  const [squadLoading, setSquadLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    return () => {
      cancelled = true;
    };
  }, [seasonId, matchdayNumber, participant.participant_id]);

  const selectedIds = useMemo(
    () => new Set(selectedPlayers.map((p) => p.player_id)),
    [selectedPlayers],
  );

  const formationCounts = useMemo(() => parseFormation(formation), [formation]);

  // Count how many of each position are currently selected
  const currentCounts = useMemo(() => {
    const c: Record<string, number> = { POR: 0, DEF: 0, MED: 0, DEL: 0 };
    for (const p of selectedPlayers) c[p.position_slot] = (c[p.position_slot] ?? 0) + 1;
    return c;
  }, [selectedPlayers]);

  function handleRemovePlayer(playerId: number) {
    setSelectedPlayers((prev) => prev.filter((p) => p.player_id !== playerId));
  }

  function handleAddPlayer(player: SquadPlayer) {
    const pos = player.position;
    const needed = formationCounts[pos] ?? 0;
    const current = currentCounts[pos] ?? 0;
    if (current >= needed) return; // position full

    setSelectedPlayers((prev) => [
      ...prev,
      {
        player_id: player.player_id,
        display_name: player.display_name,
        position_slot: pos,
        photo_path: player.photo_path,
      },
    ]);
  }

  function handleFormationChange(newFormation: string) {
    setFormation(newFormation);
    setSelectedPlayers([]);
  }

  async function handleSave() {
    if (selectedPlayers.length !== 11) {
      setError("Debes seleccionar exactamente 11 jugadores");
      return;
    }
    // Build players with position_slot like "POR", "DEF", etc.
    const players = selectedPlayers.map((p) => ({
      player_id: p.player_id,
      position_slot: p.position_slot,
    }));
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

  // PitchView players
  const pitchPlayers: PitchPlayer[] = selectedPlayers.map((p) => ({
    player_id: p.player_id,
    name: p.display_name,
    photo_path: p.photo_path,
    position_slot: p.position_slot,
  }));

  if (squadLoading) {
    return (
      <div className="mt-3 space-y-2 rounded-lg border border-vpv-border bg-vpv-bg p-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded bg-vpv-border" />
        ))}
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-vpv-accent/40 bg-vpv-bg p-4">
      {/* Formation selector */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
          Formacion
        </span>
        <div className="flex gap-1">
          {VALID_FORMATIONS.map((f) => (
            <button
              key={f}
              onClick={() => handleFormationChange(f)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                formation === f
                  ? "bg-vpv-accent text-white"
                  : "border border-vpv-border text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <span className="ml-2 text-xs text-vpv-text-muted">
          {selectedPlayers.length}/11 seleccionados
        </span>
      </div>

      {/* Pitch + Squad side by side */}
      <div className="flex flex-col gap-4 lg:flex-row">
        {/* Pitch */}
        <div className="w-full max-w-sm shrink-0">
          <PitchView
            formation={formation}
            players={pitchPlayers}
            onRemovePlayer={handleRemovePlayer}
            className="shadow-lg"
          />
          <p className="mt-1 text-center text-[10px] text-vpv-text-muted">
            Click en un jugador del campo para quitarlo
          </p>
        </div>

        {/* Squad sidebar */}
        <div className="flex-1 space-y-3">
          {POSITIONS.map((pos) => {
            const needed = formationCounts[pos] ?? 0;
            const current = currentCounts[pos] ?? 0;
            const isFull = current >= needed;
            const posPlayers = squad.filter((p) => p.position === pos);
            if (posPlayers.length === 0) return null;

            return (
              <div key={pos}>
                <div className="mb-1 flex items-center gap-2">
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${POS_COLORS[pos]}`}
                  >
                    {pos}
                  </span>
                  <span className="text-[10px] text-vpv-text-muted">
                    {current}/{needed}
                  </span>
                  {isFull && (
                    <span className="text-[10px] text-green-400">Completo</span>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                  {posPlayers.map((p) => {
                    const isSelected = selectedIds.has(p.player_id);
                    const canAdd = !isSelected && !isFull;
                    return (
                      <button
                        key={p.player_id}
                        onClick={() => canAdd && handleAddPlayer(p)}
                        disabled={isSelected || isFull}
                        className={`flex items-center gap-2 rounded-lg border px-2 py-1.5 text-left transition-colors ${
                          isSelected
                            ? "border-vpv-accent/40 bg-vpv-accent/10 opacity-50"
                            : canAdd
                              ? "border-vpv-border hover:border-vpv-accent/40 hover:bg-vpv-accent/5"
                              : "border-vpv-border/50 opacity-30"
                        }`}
                      >
                        <PlayerAvatar photoPath={p.photo_path} name={p.display_name} size={28} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium text-vpv-text">
                            {p.display_name}
                          </p>
                          <p className="text-[10px] text-vpv-text-muted">{p.team_name}</p>
                        </div>
                        <span className="shrink-0 text-xs font-medium text-vpv-text-muted">
                          {p.points_this_matchday ?? "-"} pts
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400">{error}</p>
      )}

      <div className="mt-4 flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving || selectedPlayers.length !== 11}
          className="rounded bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Guardando..." : "Guardar alineacion"}
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
// Participant card with mini pitch
// ---------------------------------------------------------------------------

interface CardProps {
  participant: ParticipantLineup;
  isEditing: boolean;
  seasonId: number;
  matchdayNumber: number;
  onToggleEdit: (id: number) => void;
  onSave: (participantId: number, result: SaveResult) => void;
  onCancel: () => void;
}

function ParticipantCard({
  participant,
  isEditing,
  seasonId,
  matchdayNumber,
  onToggleEdit,
  onSave,
  onCancel,
}: CardProps) {
  const pitchPlayers: PitchPlayer[] = participant.players.map((p) => ({
    player_id: p.player_id,
    name: p.display_name,
    photo_path: p.photo_path,
    position_slot: p.position_slot.split("-")[0],
  }));

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-start gap-4 px-4 py-3">
        {/* Mini pitch */}
        {participant.has_lineup && participant.formation && (
          <div className="hidden w-36 shrink-0 sm:block">
            <PitchView formation={participant.formation} players={pitchPlayers} className="rounded-lg" />
          </div>
        )}

        {/* Info */}
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-vpv-text">{participant.display_name}</h3>
            {participant.has_lineup ? (
              <>
                <span className="rounded bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                  {participant.formation}
                </span>
                <span className="text-sm font-bold text-vpv-text">
                  {participant.total_points} pts
                </span>
              </>
            ) : (
              <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">
                Sin alineacion
              </span>
            )}
          </div>

          {/* Player names with points */}
          {participant.has_lineup && (
            <div className="mt-2 flex flex-wrap gap-1">
              {participant.players
                .sort((a, b) => a.display_order - b.display_order)
                .map((p) => {
                  const pos = p.position_slot.split("-")[0];
                  return (
                    <span
                      key={p.player_id}
                      className={`rounded border px-1.5 py-0.5 text-[10px] ${POS_COLORS[pos] ?? "text-vpv-text-muted border-vpv-border"}`}
                    >
                      {p.display_name.split(" ").pop()}{" "}
                      <span className="font-bold">{p.points}</span>
                    </span>
                  );
                })}
            </div>
          )}
        </div>

        {/* Edit button */}
        <button
          onClick={() => onToggleEdit(participant.participant_id)}
          className={`shrink-0 rounded px-3 py-1.5 text-xs font-medium transition-colors ${
            isEditing
              ? "bg-vpv-accent text-white"
              : "border border-vpv-border text-vpv-text-muted hover:border-vpv-accent hover:text-vpv-accent"
          }`}
        >
          {isEditing ? "Cerrar" : participant.has_lineup ? "Editar" : "Crear"}
        </button>
      </div>

      {/* Inline editor */}
      {isEditing && (
        <div className="border-t border-vpv-border px-4 pb-4">
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
  const [matchdayInput, setMatchdayInput] = useState("");
  const [searchedMatchday, setSearchedMatchday] = useState<number | null>(null);
  const [lineups, setLineups] = useState<ParticipantLineup[]>([]);
  const [loading, setLoading] = useState(true);
  const [lineupsLoading, setLineupsLoading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const selectedSeason = seasons.find((s) => s.id === selectedSeasonId) ?? null;

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
        /* auth handles */
      } finally {
        setLoading(false);
      }
    }
    fetchSeasons();
  }, []);

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
      setLineups(
        [...data.participants].sort((a, b) => a.display_name.localeCompare(b.display_name)),
      );
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

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  }

  function handleSave(participantId: number, result: SaveResult) {
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
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-24 rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text"
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

      {searchedMatchday === null && !lineupsLoading && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-10 text-center text-sm text-vpv-text-muted">
          Selecciona una temporada y jornada y pulsa Buscar
        </div>
      )}

      {lineupsLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-lg bg-vpv-border" />
          ))}
        </div>
      )}

      {!lineupsLoading && searchedMatchday !== null && (
        <div className="space-y-3">
          {lineups.length === 0 && (
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-10 text-center text-sm text-vpv-text-muted">
              No hay participantes para esta jornada
            </div>
          )}
          {lineups.map((p) => (
            <ParticipantCard
              key={p.participant_id}
              participant={p}
              isEditing={editingId === p.participant_id}
              seasonId={selectedSeasonId!}
              matchdayNumber={searchedMatchday}
              onToggleEdit={(id) => setEditingId((prev) => (prev === id ? null : id))}
              onSave={handleSave}
              onCancel={() => setEditingId(null)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
