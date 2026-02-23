"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { SquadDetailResponse, SquadPlayerEntry } from "@/types";

const POSITION_ORDER = ["POR", "DEF", "MED", "DEL"];
const POSITION_COLORS: Record<string, string> = {
  POR: "bg-amber-500/20 text-amber-400",
  DEF: "bg-blue-500/20 text-blue-400",
  MED: "bg-green-500/20 text-green-400",
  DEL: "bg-red-500/20 text-red-400",
};

function groupByPosition(players: SquadPlayerEntry[]) {
  const groups: Record<string, SquadPlayerEntry[]> = {};
  for (const pos of POSITION_ORDER) {
    groups[pos] = players.filter((p) => p.position === pos);
  }
  return groups;
}

export default function PlantillaDetailPage() {
  const { participantId } = useParams<{ participantId: string }>();
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<SquadDetailResponse>(
    selectedSeason && participantId
      ? `/squads/${selectedSeason.id}/${participantId}`
      : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-vpv-text-muted">Cargando plantilla...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar la plantilla.
      </div>
    );
  }

  const grouped = groupByPosition(data.players);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href="/plantillas"
          className="text-vpv-text-muted transition-colors hover:text-vpv-text"
        >
          Plantillas
        </Link>
        <span className="text-vpv-text-muted">/</span>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-vpv-text">
          {data.display_name}
        </h1>
        <span className="text-xl font-bold tabular-nums text-vpv-accent">
          {data.season_points} pts
        </span>
      </div>

      <p className="text-sm text-vpv-text-muted">
        {data.players.length} jugadores
      </p>

      <div className="space-y-6">
        {POSITION_ORDER.map((pos) => {
          const players = grouped[pos];
          if (!players || players.length === 0) return null;

          return (
            <div key={pos}>
              <div className="mb-2 flex items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-xs font-bold ${POSITION_COLORS[pos] ?? ""}`}
                >
                  {pos}
                </span>
                <span className="text-xs text-vpv-text-muted">
                  {players.length}
                </span>
              </div>

              <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
                      <th className="px-4 py-2">Jugador</th>
                      <th className="px-4 py-2">Equipo</th>
                      <th className="px-4 py-2 text-right">Pts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {players.map((player) => (
                      <tr
                        key={player.player_id}
                        className="border-b border-vpv-border last:border-0 hover:bg-vpv-accent/5"
                      >
                        <td className="px-4 py-2 font-medium text-vpv-text">
                          {player.display_name}
                        </td>
                        <td className="px-4 py-2 text-vpv-text-muted">
                          {player.team_name}
                        </td>
                        <td className="px-4 py-2 text-right font-bold tabular-nums text-vpv-text">
                          {player.season_points}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
