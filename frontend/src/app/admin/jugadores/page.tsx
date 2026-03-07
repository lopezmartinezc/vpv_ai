"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { useSeason } from "@/contexts/season-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Team {
  id: number;
  name: string;
}

interface Player {
  id: number;
  display_name: string;
  slug: string;
  position: string;
  team_id: number;
  team_name: string;
  owner_name: string | null;
  is_available: boolean;
}

interface PlayersResponse {
  season_id: number;
  players: Player[];
  total: number;
}

interface TeamsResponse {
  teams: Team[];
}

interface PatchPlayerResponse {
  id: number;
  display_name: string;
  team_id: number;
  team_name: string;
  position: string;
}

type Position = "POR" | "DEF" | "MED" | "DEL";

const POSITIONS: Position[] = ["POR", "DEF", "MED", "DEL"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Maps a position code to a readable label with a subtle badge style. */
function positionBadgeClass(pos: string): string {
  switch (pos) {
    case "POR":
      return "bg-yellow-500/20 text-yellow-400";
    case "DEF":
      return "bg-blue-500/20 text-blue-400";
    case "MED":
      return "bg-green-500/20 text-green-400";
    case "DEL":
      return "bg-red-500/20 text-red-400";
    default:
      return "bg-vpv-border text-vpv-text-muted";
  }
}

// ---------------------------------------------------------------------------
// Inline edit cell — position
// ---------------------------------------------------------------------------

interface PositionCellProps {
  playerId: number;
  value: string;
  onSave: (playerId: number, position: Position) => Promise<void>;
  saving: boolean;
}

function PositionCell({ playerId, value, onSave, saving }: PositionCellProps) {
  const [editing, setEditing] = useState(false);

  if (!editing) {
    return (
      <button
        onClick={() => setEditing(true)}
        aria-label={`Editar posicion de jugador ${playerId}`}
        className={`rounded px-2 py-0.5 text-xs font-medium transition-opacity hover:opacity-75 ${positionBadgeClass(value)}`}
      >
        {value}
      </button>
    );
  }

  return (
    <select
      autoFocus
      value={value}
      disabled={saving}
      aria-label="Seleccionar posicion"
      onChange={async (e) => {
        setEditing(false);
        await onSave(playerId, e.target.value as Position);
      }}
      onBlur={() => setEditing(false)}
      className="rounded border border-vpv-border bg-vpv-bg px-1 py-0.5 text-xs text-vpv-text focus:border-vpv-accent focus:outline-none disabled:opacity-50"
    >
      {POSITIONS.map((p) => (
        <option key={p} value={p}>
          {p}
        </option>
      ))}
    </select>
  );
}

// ---------------------------------------------------------------------------
// Inline edit cell — team
// ---------------------------------------------------------------------------

interface TeamCellProps {
  playerId: number;
  value: string;
  teams: Team[];
  onSave: (playerId: number, teamId: number) => Promise<void>;
  saving: boolean;
}

function TeamCell({ playerId, value, teams, onSave, saving }: TeamCellProps) {
  const [editing, setEditing] = useState(false);

  const currentTeam = teams.find((t) => t.name === value);

  if (!editing) {
    return (
      <button
        onClick={() => setEditing(true)}
        aria-label={`Editar equipo de jugador ${playerId}`}
        className="max-w-[160px] truncate text-left text-vpv-text underline-offset-2 hover:underline"
      >
        {value}
      </button>
    );
  }

  return (
    <select
      autoFocus
      defaultValue={currentTeam?.id ?? ""}
      disabled={saving}
      aria-label="Seleccionar equipo"
      onChange={async (e) => {
        setEditing(false);
        const id = Number(e.target.value);
        if (id) await onSave(playerId, id);
      }}
      onBlur={() => setEditing(false)}
      className="rounded border border-vpv-border bg-vpv-bg px-1 py-0.5 text-xs text-vpv-text focus:border-vpv-accent focus:outline-none disabled:opacity-50"
    >
      {teams.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name}
        </option>
      ))}
    </select>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminJugadoresPage() {
  // Season comes from the global context (the active / user-selected season)
  const { seasons, selectedSeason, selectSeason, loading: seasonsLoading } = useSeason();

  const [teams, setTeams] = useState<Team[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [loadingPlayers, setLoadingPlayers] = useState(false);
  const [loadingTeams, setLoadingTeams] = useState(false);

  // Filters (client-side)
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState<string>("");

  // Per-row save state: playerId -> true while PATCH in-flight
  const [savingMap, setSavingMap] = useState<Record<number, boolean>>({});

  // Briefly highlight rows after a successful save
  const [savedMap, setSavedMap] = useState<Record<number, boolean>>({});

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------

  const fetchTeams = useCallback(async (seasonId: number) => {
    setLoadingTeams(true);
    try {
      const data = await apiClient.get<TeamsResponse>(
        `/players/teams/${seasonId}`,
      );
      setTeams(data.teams);
    } catch {
      // errors surfaced by auth context
    } finally {
      setLoadingTeams(false);
    }
  }, []);

  const fetchPlayers = useCallback(async (seasonId: number) => {
    setLoadingPlayers(true);
    try {
      const data = await apiClient.get<PlayersResponse>(
        `/players/${seasonId}`,
      );
      setPlayers(data.players);
    } catch {
      // errors surfaced by auth context
    } finally {
      setLoadingPlayers(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedSeason) return;
    fetchTeams(selectedSeason.id);
    fetchPlayers(selectedSeason.id);
  }, [selectedSeason, fetchTeams, fetchPlayers]);

  // ---------------------------------------------------------------------------
  // Client-side filtering
  // ---------------------------------------------------------------------------

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return players.filter((p) => {
      if (q && !p.display_name.toLowerCase().includes(q)) return false;
      if (teamFilter && p.team_name !== teamFilter) return false;
      return true;
    });
  }, [players, search, teamFilter]);

  // ---------------------------------------------------------------------------
  // Patch helpers
  // ---------------------------------------------------------------------------

  async function patchPlayer(
    playerId: number,
    body: { team_id?: number; position?: string },
  ) {
    setSavingMap((prev) => ({ ...prev, [playerId]: true }));
    try {
      const updated = await apiClient.patch<PatchPlayerResponse>(
        `/players/${playerId}`,
        body,
      );
      setPlayers((prev) =>
        prev.map((p) =>
          p.id === updated.id
            ? {
                ...p,
                team_id: updated.team_id,
                team_name: updated.team_name,
                position: updated.position,
              }
            : p,
        ),
      );
      // Show success flash for 2 s
      setSavedMap((prev) => ({ ...prev, [playerId]: true }));
      setTimeout(
        () => setSavedMap((prev) => ({ ...prev, [playerId]: false })),
        2000,
      );
    } catch {
      // errors surfaced by auth context / toast layer
    } finally {
      setSavingMap((prev) => ({ ...prev, [playerId]: false }));
    }
  }

  const handleSavePosition = useCallback(
    async (playerId: number, position: Position) => {
      await patchPlayer(playerId, { position });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const handleSaveTeam = useCallback(
    async (playerId: number, teamId: number) => {
      await patchPlayer(playerId, { team_id: teamId });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // ---------------------------------------------------------------------------
  // Loading states
  // ---------------------------------------------------------------------------

  if (seasonsLoading) {
    return (
      <div className="flex min-h-[20vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const isLoading = loadingPlayers || loadingTeams;

  return (
    <div className="space-y-4">
      {/* ------------------------------------------------------------------ */}
      {/* Filters bar                                                          */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-wrap items-end gap-3">
        {/* Season selector */}
        <div>
          <label
            htmlFor="season-select"
            className="mb-1 block text-xs text-vpv-text-muted"
          >
            Temporada
          </label>
          <select
            id="season-select"
            value={selectedSeason?.id ?? ""}
            onChange={(e) => selectSeason(Number(e.target.value))}
            className="rounded-md border border-vpv-border bg-vpv-card px-3 py-1.5 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
          >
            {seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {s.status === "active" ? " (actual)" : ""}
              </option>
            ))}
          </select>
        </div>

        {/* Search */}
        <div className="flex-1 min-w-[160px]">
          <label
            htmlFor="player-search"
            className="mb-1 block text-xs text-vpv-text-muted"
          >
            Buscar jugador
          </label>
          <input
            id="player-search"
            type="search"
            placeholder="Nombre..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-vpv-border bg-vpv-card px-3 py-1.5 text-sm text-vpv-text placeholder-vpv-text-muted focus:border-vpv-accent focus:outline-none"
          />
        </div>

        {/* Team filter */}
        <div>
          <label
            htmlFor="team-filter"
            className="mb-1 block text-xs text-vpv-text-muted"
          >
            Equipo
          </label>
          <select
            id="team-filter"
            value={teamFilter}
            onChange={(e) => setTeamFilter(e.target.value)}
            disabled={loadingTeams}
            className="rounded-md border border-vpv-border bg-vpv-card px-3 py-1.5 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none disabled:opacity-50"
          >
            <option value="">Todos los equipos</option>
            {teams.map((t) => (
              <option key={t.id} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Table card                                                           */}
      {/* ------------------------------------------------------------------ */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Jugadores
            {!isLoading && (
              <span className="ml-2 text-sm font-normal text-vpv-text-muted">
                ({filtered.length}
                {filtered.length !== players.length
                  ? ` de ${players.length}`
                  : ""}
                )
              </span>
            )}
          </h2>
          {isLoading && (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
          )}
        </div>

        {/* Loading skeleton */}
        {isLoading && players.length === 0 && (
          <div className="space-y-px py-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <div
                key={i}
                className="mx-4 h-10 animate-pulse rounded bg-vpv-border"
              />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && filtered.length === 0 && (
          <p className="px-4 py-8 text-center text-sm text-vpv-text-muted">
            {players.length === 0
              ? "No hay jugadores para esta temporada."
              : "Ningun jugador coincide con los filtros."}
          </p>
        )}

        {/* Mobile: Cards */}
        {filtered.length > 0 && (
          <div className="divide-y divide-vpv-border md:hidden">
            {filtered.map((player) => (
              <div
                key={player.id}
                className={`space-y-2 px-4 py-3 transition-colors ${
                  savedMap[player.id] ? "bg-vpv-accent/5" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-vpv-text">
                      {player.display_name}
                    </p>
                    <p className="text-xs text-vpv-text-muted">
                      {player.owner_name ?? (
                        <span className="italic">Libre</span>
                      )}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {savedMap[player.id] && (
                      <span className="rounded bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                        Guardado
                      </span>
                    )}
                    {!player.is_available && !player.owner_name && (
                      <span className="rounded bg-vpv-border px-2 py-0.5 text-xs text-vpv-text-muted">
                        No disp.
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-vpv-text-muted">Pos:</span>
                    <PositionCell
                      playerId={player.id}
                      value={player.position}
                      onSave={handleSavePosition}
                      saving={!!savingMap[player.id]}
                    />
                  </div>
                  <div className="flex min-w-0 flex-1 items-center gap-1.5">
                    <span className="shrink-0 text-xs text-vpv-text-muted">
                      Equipo:
                    </span>
                    <TeamCell
                      playerId={player.id}
                      value={player.team_name}
                      teams={teams}
                      onSave={handleSaveTeam}
                      saving={!!savingMap[player.id]}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Desktop: Table */}
        {filtered.length > 0 && (
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
                  <th className="px-4 py-2 font-medium">Nombre</th>
                  <th className="px-4 py-2 font-medium">Posicion</th>
                  <th className="px-4 py-2 font-medium">Equipo</th>
                  <th className="px-4 py-2 font-medium">Propietario</th>
                  <th className="px-4 py-2 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((player) => (
                  <tr
                    key={player.id}
                    className={`border-b border-vpv-border last:border-0 transition-colors ${
                      savedMap[player.id]
                        ? "bg-vpv-accent/5"
                        : "hover:bg-vpv-bg/50"
                    }`}
                  >
                    {/* Name */}
                    <td className="px-4 py-2 font-medium text-vpv-text">
                      {player.display_name}
                    </td>

                    {/* Position — inline editable */}
                    <td className="px-4 py-2">
                      <PositionCell
                        playerId={player.id}
                        value={player.position}
                        onSave={handleSavePosition}
                        saving={!!savingMap[player.id]}
                      />
                    </td>

                    {/* Team — inline editable */}
                    <td className="px-4 py-2">
                      <TeamCell
                        playerId={player.id}
                        value={player.team_name}
                        teams={teams}
                        onSave={handleSaveTeam}
                        saving={!!savingMap[player.id]}
                      />
                    </td>

                    {/* Owner */}
                    <td className="px-4 py-2 text-vpv-text-muted">
                      {player.owner_name ?? (
                        <span className="italic">Libre</span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="px-4 py-2">
                      {savedMap[player.id] ? (
                        <span className="rounded bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                          Guardado
                        </span>
                      ) : savingMap[player.id] ? (
                        <span className="rounded bg-vpv-border px-2 py-0.5 text-xs text-vpv-text-muted">
                          Guardando...
                        </span>
                      ) : player.is_available ? (
                        <span className="text-xs text-vpv-text-muted">
                          Libre
                        </span>
                      ) : (
                        <span className="text-xs text-vpv-text-muted">
                          {player.owner_name ?? "No disp."}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
