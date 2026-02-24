"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { DraftDetailResponse } from "@/types";

const PHASE_LABELS: Record<string, string> = {
  preseason: "Pretemporada",
  winter: "Invierno",
};

const POSITION_COLORS: Record<string, string> = {
  POR: "text-amber-400",
  DEF: "text-blue-400",
  MED: "text-green-400",
  DEL: "text-red-400",
};

export default function DraftDetailPage() {
  const { phase } = useParams<{ phase: string }>();
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<DraftDetailResponse>(
    selectedSeason && phase
      ? `/drafts/${selectedSeason.id}/${phase}`
      : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-vpv-text-muted">Cargando draft...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar el draft.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href="/drafts"
          className="text-vpv-text-muted transition-colors hover:text-vpv-text"
        >
          Drafts
        </Link>
        <span className="text-vpv-text-muted">/</span>
      </div>

      <h1 className="text-2xl font-bold text-vpv-text">
        Draft {PHASE_LABELS[data.phase] ?? data.phase}
      </h1>

      <p className="text-sm text-vpv-text-muted">
        {data.picks.length} picks &middot;{" "}
        {data.participants.length} participantes
      </p>

      <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="w-14 px-4 py-2 text-center">#</th>
              <th className="w-14 px-4 py-2 text-center">Ronda</th>
              <th className="px-4 py-2">Participante</th>
              <th className="px-4 py-2">Jugador</th>
              <th className="w-14 px-4 py-2 text-center">Pos</th>
              <th className="px-4 py-2">Equipo</th>
            </tr>
          </thead>
          <tbody>
            {data.picks.map((pick) => (
              <tr
                key={pick.pick_number}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-accent/5"
              >
                <td className="px-4 py-2 text-center tabular-nums text-vpv-text-muted">
                  {pick.pick_number}
                </td>
                <td className="px-4 py-2 text-center tabular-nums text-vpv-text-muted">
                  {pick.round_number}
                </td>
                <td className="px-4 py-2 font-medium text-vpv-text">
                  {pick.display_name}
                </td>
                <td className="px-4 py-2 text-vpv-text">
                  {pick.player_name}
                </td>
                <td
                  className={`px-4 py-2 text-center text-xs font-bold ${POSITION_COLORS[pick.position] ?? ""}`}
                >
                  {pick.position}
                </td>
                <td className="px-4 py-2 text-vpv-text-muted">
                  {pick.team_name}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
