"use client";

import { useState } from "react";
import type {
  ParticipantBreakdown,
  ParticipantExtremes,
} from "@/types";

export function ParticipantsTab({
  breakdowns,
  extremes,
}: {
  breakdowns: ParticipantBreakdown[];
  extremes: ParticipantExtremes[];
}) {
  const [view, setView] = useState<"breakdown" | "extremes">(
    "breakdown",
  );

  return (
    <div className="space-y-3">
      <div className="flex gap-1">
        {(
          [
            { key: "breakdown", label: "Desglose" },
            { key: "extremes", label: "Extremos" },
          ] as const
        ).map((v) => (
          <button
            key={v.key}
            onClick={() => setView(v.key)}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              view === v.key
                ? "bg-vpv-accent text-white"
                : "bg-vpv-bg text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {view === "breakdown" && <BreakdownTable breakdowns={breakdowns} />}
      {view === "extremes" && <ExtremesTable extremes={extremes} />}
    </div>
  );
}

function BreakdownTable({
  breakdowns,
}: {
  breakdowns: ParticipantBreakdown[];
}) {
  if (breakdowns.length === 0) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-6 text-sm text-vpv-text-muted">
        Sin desglose todavia: aparecera cuando haya jornadas puntuadas.
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-bg text-left text-xs text-vpv-text-muted">
              <th className="px-3 py-2">Participante</th>
              <th className="px-3 py-2 text-right">Juega</th>
              <th className="px-3 py-2 text-right">Resultado</th>
              <th className="px-3 py-2 text-right">P. imbatida</th>
              <th className="px-3 py-2 text-right">Goles</th>
              <th className="px-3 py-2 text-right">Asist.</th>
              <th className="px-3 py-2 text-right">Amarillas</th>
              <th className="px-3 py-2 text-right">Rojas</th>
              <th className="px-3 py-2 text-right">Marca/AS</th>
              <th className="px-3 py-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {breakdowns.map((b) => (
              <tr
                key={b.participant_id}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
              >
                <td className="px-3 py-1.5 font-medium text-vpv-text">
                  {b.display_name}
                </td>
                <td className="px-3 py-1.5 text-right text-vpv-text-muted">
                  {b.pts_play}
                </td>
                <td className="px-3 py-1.5 text-right text-vpv-text-muted">
                  {b.pts_result}
                </td>
                <td className="px-3 py-1.5 text-right text-vpv-text-muted">
                  {b.pts_clean_sheet}
                </td>
                <td className="px-3 py-1.5 text-right text-vpv-text">
                  {b.pts_goals}
                </td>
                <td className="px-3 py-1.5 text-right text-vpv-text">
                  {b.pts_assists}
                </td>
                <td className="px-3 py-1.5 text-right text-yellow-400">
                  {b.pts_yellow}
                </td>
                <td className="px-3 py-1.5 text-right text-red-400">
                  {b.pts_red}
                </td>
                <td className="px-3 py-1.5 text-right text-vpv-text-muted">
                  {b.pts_marca_as}
                </td>
                <td className="px-3 py-1.5 text-right font-medium text-vpv-accent">
                  {b.pts_total}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ExtremesTable({ extremes }: { extremes: ParticipantExtremes[] }) {
  if (extremes.length === 0) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-6 text-sm text-vpv-text-muted">
        Sin extremos todavia: aparecera cuando haya jornadas puntuadas.
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-bg text-left text-xs text-vpv-text-muted">
              <th className="px-3 py-2">Participante</th>
              <th className="px-3 py-2 text-right">Mejor</th>
              <th className="px-3 py-2 text-right">Jornada</th>
              <th className="px-3 py-2 text-right">Peor</th>
              <th className="px-3 py-2 text-right">Jornada</th>
              <th className="px-3 py-2 text-right">Media</th>
            </tr>
          </thead>
          <tbody>
            {extremes.map((e) => (
              <tr
                key={e.participant_id}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
              >
                <td className="px-3 py-1.5 font-medium text-vpv-text">
                  {e.display_name}
                </td>
                <td className="px-3 py-1.5 text-right font-medium text-green-400">
                  {e.best_points}
                </td>
                <td className="px-3 py-1.5 text-right text-vpv-text-muted">
                  J{e.best_matchday}
                </td>
                <td className="px-3 py-1.5 text-right font-medium text-red-400">
                  {e.worst_points}
                </td>
                <td className="px-3 py-1.5 text-right text-vpv-text-muted">
                  J{e.worst_matchday}
                </td>
                <td className="px-3 py-1.5 text-right font-medium text-vpv-accent">
                  {e.avg_points.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// League Tab
// ---------------------------------------------------------------------------

/**
 * LeagueTab — League-wide stats:
 *  - Records cards (best/worst individual, best/worst avg matchday)
 *  - Formation usage horizontal bar chart
 *  - Matchday averages table
 */
