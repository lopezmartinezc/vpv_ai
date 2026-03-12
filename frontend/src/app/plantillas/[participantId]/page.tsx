"use client";

import { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SkeletonTable } from "@/components/ui/skeleton";
import type { SquadDetailResponse, SquadPlayerEntry } from "@/types";
import { PlayerAvatar } from "@/components/ui/player-avatar";

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
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <div className="h-4 w-32 animate-pulse rounded bg-vpv-border" />
          <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />
          <SkeletonTable rows={6} />
          <SkeletonTable rows={6} />
        </div>
      }
    >
      <PlantillaDetailContent />
    </Suspense>
  );
}

function PlantillaDetailContent() {
  const { participantId } = useParams<{ participantId: string }>();
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const searchParams = useSearchParams();
  const jornada = searchParams.get("jornada");

  const apiPath =
    selectedSeason && participantId
      ? `/squads/${selectedSeason.id}/${participantId}${jornada ? `?matchday=${jornada}` : ""}`
      : null;

  const { data, loading } = useFetch<SquadDetailResponse>(apiPath);

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-4 w-32 animate-pulse rounded bg-vpv-border" />
        <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={6} />
        <SkeletonTable rows={6} />
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
  const backHref = `/plantillas${jornada ? `?jornada=${jornada}` : ""}`;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href={backHref}
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
        {jornada && ` (jornada ${jornada})`}
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

              {/* Mobile: Cards */}
              <div className="space-y-1.5 md:hidden">
                {players.map((player) => (
                  <div
                    key={player.player_id}
                    className="flex items-center justify-between rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5"
                  >
                    <PlayerAvatar photoPath={player.photo_path} name={player.display_name} size={48} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-vpv-text">
                        {player.display_name}
                      </p>
                      <p className="text-xs text-vpv-text-muted">
                        {player.team_name}
                      </p>
                    </div>
                    <span className="ml-3 font-bold tabular-nums text-vpv-text">
                      {player.season_points}
                    </span>
                  </div>
                ))}
              </div>

              {/* Desktop: Table */}
              <div className="hidden overflow-x-auto rounded-lg border border-vpv-card-border md:block">
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
                        <td className="px-4 py-2">
                          <span className="flex items-center gap-2 font-medium text-vpv-text">
                            <PlayerAvatar photoPath={player.photo_path} name={player.display_name} size={48} />
                            {player.display_name}
                          </span>
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
