"use client";

import { useMemo, useState } from "react";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { DraftPickEntry } from "@/types";

const POSITION_COLORS: Record<string, string> = {
  POR: "bg-amber-600/20 text-amber-400",
  DEF: "bg-blue-600/20 text-blue-400",
  MED: "bg-green-600/20 text-green-400",
  DEL: "bg-red-600/20 text-red-400",
};

const POSITIONS = ["POR", "DEF", "MED", "DEL"];

const PARTICIPANT_COLORS = [
  "bg-blue-500/15 text-blue-400",
  "bg-emerald-500/15 text-emerald-400",
  "bg-amber-500/15 text-amber-400",
  "bg-red-500/15 text-red-400",
  "bg-purple-500/15 text-purple-400",
  "bg-cyan-500/15 text-cyan-400",
  "bg-pink-500/15 text-pink-400",
  "bg-orange-500/15 text-orange-400",
  "bg-lime-500/15 text-lime-400",
  "bg-indigo-500/15 text-indigo-400",
  "bg-teal-500/15 text-teal-400",
  "bg-rose-500/15 text-rose-400",
  "bg-sky-500/15 text-sky-400",
];

export function PicksList({ picks }: { picks: DraftPickEntry[] }) {
  const [filterParticipantId, setFilterParticipantId] = useState<number | null>(null);
  const [filterPosition, setFilterPosition] = useState<string | null>(null);
  const [filterTeam, setFilterTeam] = useState<string | null>(null);
  const [searchPlayer, setSearchPlayer] = useState("");

  // Build unique participants in order of first appearance
  const participants = useMemo(() => {
    const map = new Map<number, { id: number; name: string }>();
    for (const pick of picks) {
      if (!map.has(pick.participant_id)) {
        map.set(pick.participant_id, { id: pick.participant_id, name: pick.display_name });
      }
    }
    return [...map.values()];
  }, [picks]);

  // Build unique teams sorted alphabetically
  const teams = useMemo(() => {
    const set = new Set<string>();
    for (const pick of picks) set.add(pick.team_name);
    return [...set].sort();
  }, [picks]);

  function getParticipantColor(participantId: number): string {
    const idx = participants.findIndex((p) => p.id === participantId);
    return PARTICIPANT_COLORS[(idx >= 0 ? idx : 0) % PARTICIPANT_COLORS.length];
  }

  const displayPicks = useMemo(() => {
    const normalizedSearch = searchPlayer.toLowerCase().trim();
    return picks.filter((p) => {
      if (filterParticipantId !== null && p.participant_id !== filterParticipantId) return false;
      if (filterPosition !== null && p.position !== filterPosition) return false;
      if (filterTeam !== null && p.team_name !== filterTeam) return false;
      if (normalizedSearch && !p.player_name.toLowerCase().includes(normalizedSearch)) return false;
      return true;
    });
  }, [picks, filterParticipantId, filterPosition, filterTeam, searchPlayer]);

  const hasFilters = filterParticipantId !== null || filterPosition !== null || filterTeam !== null || searchPlayer !== "";

  function clearFilters() {
    setFilterParticipantId(null);
    setFilterPosition(null);
    setFilterTeam(null);
    setSearchPlayer("");
  }

  return (
    <div className="space-y-4">
      {/* Search + dropdown filters */}
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="Buscar jugador..."
          value={searchPlayer}
          onChange={(e) => setSearchPlayer(e.target.value)}
          className="w-full rounded-lg border border-vpv-border bg-vpv-card px-3 py-2 text-sm text-vpv-text placeholder:text-vpv-text-muted/50 focus:border-vpv-accent focus:outline-none sm:w-48"
        />
        <select
          value={filterPosition ?? ""}
          onChange={(e) => setFilterPosition(e.target.value || null)}
          className="rounded-lg border border-vpv-border bg-vpv-card px-3 py-2 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
        >
          <option value="">Posicion</option>
          {POSITIONS.map((pos) => (
            <option key={pos} value={pos}>{pos}</option>
          ))}
        </select>
        <select
          value={filterTeam ?? ""}
          onChange={(e) => setFilterTeam(e.target.value || null)}
          className="rounded-lg border border-vpv-border bg-vpv-card px-3 py-2 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
        >
          <option value="">Equipo</option>
          {teams.map((team) => (
            <option key={team} value={team}>{team}</option>
          ))}
        </select>
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="rounded-lg border border-vpv-border px-3 py-2 text-xs font-medium text-vpv-text-muted transition-colors hover:text-vpv-text"
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {/* Participant chips */}
      {participants.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilterParticipantId(null)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              filterParticipantId === null
                ? "bg-vpv-accent text-white"
                : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            Todos ({picks.length})
          </button>
          {participants.map((p) => {
            const count = picks.filter((pk) => pk.participant_id === p.id).length;
            const isActive = filterParticipantId === p.id;
            const color = getParticipantColor(p.id);
            return (
              <button
                key={p.id}
                onClick={() => setFilterParticipantId(isActive ? null : p.id)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive ? "bg-vpv-accent text-white" : `${color} hover:brightness-125`
                }`}
              >
                {p.name} ({count})
              </button>
            );
          })}
        </div>
      )}

      {/* Results count */}
      {hasFilters && (
        <p className="text-xs text-vpv-text-muted">
          {displayPicks.length} de {picks.length} picks
        </p>
      )}

      {/* Mobile: Cards */}
      <div className="space-y-1.5 md:hidden">
        {displayPicks.map((pick) => (
          <div
            key={pick.id}
            className="flex items-center gap-3 rounded-lg border border-vpv-card-border bg-vpv-card px-3 py-2.5"
          >
            <span className="w-6 text-center text-xs tabular-nums text-vpv-text-muted">
              {pick.pick_number}
            </span>
            <PlayerAvatar
              photoPath={pick.photo_path}
              name={pick.player_name}
              size={32}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-vpv-text">
                {pick.player_name}
              </p>
              <p className="text-xs text-vpv-text-muted">
                <span
                  className={`inline-block rounded px-1 py-0.5 text-[10px] font-semibold ${POSITION_COLORS[pick.position] ?? ""}`}
                >
                  {pick.position}
                </span>{" "}
                {pick.team_name}
              </p>
            </div>
            <div className="text-right">
              <span
                className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${getParticipantColor(pick.participant_id)}`}
              >
                {pick.display_name}
              </span>
              <p className="mt-0.5 text-[10px] text-vpv-text-muted">
                R{pick.round_number}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden overflow-x-auto rounded-lg border border-vpv-card-border md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-xs text-vpv-text-muted">
              <th className="w-12 px-3 py-2.5 text-center">#</th>
              <th className="w-12 px-3 py-2.5 text-center">Rda</th>
              <th className="px-3 py-2.5">Participante</th>
              <th className="px-3 py-2.5">Jugador</th>
              <th className="w-12 px-3 py-2.5 text-center">Pos</th>
              <th className="px-3 py-2.5">Equipo</th>
            </tr>
          </thead>
          <tbody>
            {displayPicks.map((pick, i) => {
              const showRoundSep =
                !hasFilters &&
                i > 0 &&
                displayPicks[i - 1].round_number !== pick.round_number;

              return (
                <tr
                  key={pick.id}
                  className={`border-b border-vpv-border last:border-0 hover:bg-vpv-accent/5 ${
                    showRoundSep ? "border-t-2 border-t-vpv-border" : ""
                  }`}
                >
                  <td className="px-3 py-2 text-center tabular-nums text-vpv-text-muted">
                    {pick.pick_number}
                  </td>
                  <td className="px-3 py-2 text-center tabular-nums text-vpv-text-muted">
                    {pick.round_number}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${getParticipantColor(pick.participant_id)}`}
                    >
                      {pick.display_name}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <PlayerAvatar
                        photoPath={pick.photo_path}
                        name={pick.player_name}
                        size={28}
                      />
                      <span className="font-medium text-vpv-text">
                        {pick.player_name}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span
                      className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold ${POSITION_COLORS[pick.position] ?? ""}`}
                    >
                      {pick.position}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-vpv-text-muted">
                    {pick.team_name}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {displayPicks.length === 0 && (
        <p className="py-8 text-center text-sm text-vpv-text-muted">
          {hasFilters ? "Sin resultados para estos filtros." : "No hay picks registrados."}
        </p>
      )}
    </div>
  );
}
