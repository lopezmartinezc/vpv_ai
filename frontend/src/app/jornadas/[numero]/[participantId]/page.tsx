"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { LineupDetailResponse, LineupPlayerEntry } from "@/types";

export default function LineupDetailPage() {
  const params = useParams<{ numero: string; participantId: string }>();
  const numero = Number(params.numero);
  const participantId = Number(params.participantId);
  const { selectedSeason, loading: seasonLoading } = useSeason();

  const { data, loading } = useFetch<LineupDetailResponse>(
    selectedSeason
      ? `/matchdays/${selectedSeason.id}/${numero}/lineup/${participantId}`
      : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-vpv-text-muted">Cargando alineacion...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar la alineacion.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-vpv-text-muted">
        <Link href="/jornadas" className="transition-colors hover:text-vpv-text">
          Jornadas
        </Link>
        <span>/</span>
        <Link
          href={`/jornadas/${numero}`}
          className="transition-colors hover:text-vpv-text"
        >
          Jornada {numero}
        </Link>
        <span>/</span>
        <span className="text-vpv-text">{data.display_name}</span>
      </nav>

      {/* Header */}
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-vpv-text">
          {data.display_name}
        </h1>
        <div className="text-right">
          <p className="text-3xl font-bold tabular-nums text-vpv-accent">
            {data.total_points}
          </p>
          <p className="text-xs text-vpv-text-muted">{data.formation}</p>
        </div>
      </div>

      {/* Players table */}
      <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="px-3 py-3">Pos</th>
              <th className="px-3 py-3">Jugador</th>
              <th className="hidden px-3 py-3 sm:table-cell">Equipo</th>
              <th className="hidden px-2 py-3 text-center md:table-cell">
                Jug
              </th>
              <th className="hidden px-2 py-3 text-center md:table-cell">
                Res
              </th>
              <th className="hidden px-2 py-3 text-center md:table-cell">
                Gol
              </th>
              <th className="hidden px-2 py-3 text-center md:table-cell">
                Asi
              </th>
              <th className="hidden px-2 py-3 text-center md:table-cell">
                Imb
              </th>
              <th className="hidden px-2 py-3 text-center md:table-cell">
                Tar
              </th>
              <th className="hidden px-2 py-3 text-center md:table-cell">
                Val
              </th>
              <th className="px-3 py-3 text-right">Pts</th>
            </tr>
          </thead>
          <tbody>
            {data.players.map((p) => (
              <PlayerRow key={p.player_id} player={p} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PlayerRow({ player }: { player: LineupPlayerEntry }) {
  const b = player.score_breakdown;
  return (
    <tr className="border-b border-vpv-border last:border-0">
      <td className="px-3 py-2.5">
        <span className="rounded bg-vpv-card px-1.5 py-0.5 text-xs font-medium text-vpv-text-muted">
          {player.position_slot}
        </span>
      </td>
      <td className="px-3 py-2.5 font-medium text-vpv-text">
        {player.player_name}
      </td>
      <td className="hidden px-3 py-2.5 text-vpv-text-muted sm:table-cell">
        {player.team_name}
      </td>
      <td className="hidden px-2 py-2.5 text-center tabular-nums md:table-cell">
        {b ? b.pts_play + b.pts_starter : "–"}
      </td>
      <td className="hidden px-2 py-2.5 text-center tabular-nums md:table-cell">
        {b?.pts_result ?? "–"}
      </td>
      <td className="hidden px-2 py-2.5 text-center tabular-nums md:table-cell">
        {b?.pts_goals ?? "–"}
      </td>
      <td className="hidden px-2 py-2.5 text-center tabular-nums md:table-cell">
        {b?.pts_assists ?? "–"}
      </td>
      <td className="hidden px-2 py-2.5 text-center tabular-nums md:table-cell">
        {b?.pts_clean_sheet ?? "–"}
      </td>
      <td className="hidden px-2 py-2.5 text-center tabular-nums md:table-cell">
        {b ? b.pts_yellow + b.pts_red : "–"}
      </td>
      <td className="hidden px-2 py-2.5 text-center tabular-nums md:table-cell">
        {b ? b.pts_marca + b.pts_as : "–"}
      </td>
      <td className="px-3 py-2.5 text-right font-bold tabular-nums text-vpv-text">
        {player.points}
      </td>
    </tr>
  );
}
