"use client";

import { useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SkeletonTable } from "@/components/ui/skeleton";
import type {
  AccuracyMatchdayRankingEntry,
  AccuracyRankingResponse,
  MatchdayListResponse,
} from "@/types";

const RANK_BADGES: Record<number, string> = {
  1: "bg-amber-400 text-black",
  2: "bg-gray-300 text-black",
  3: "bg-amber-700 text-white",
};

const POS_COLORS: Record<string, string> = {
  POR: "text-amber-400",
  DEF: "text-blue-400",
  MED: "text-green-400",
  DEL: "text-red-400",
};

function AccuracyBar({ pct }: { pct: number }) {
  const color =
    pct >= 90 ? "bg-emerald-500" : pct >= 70 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="h-2.5 w-full rounded-full bg-vpv-border overflow-hidden">
      <div
        className={`h-full rounded-full ${color}`}
        style={{ width: `${Math.min(100, pct)}%` }}
      />
    </div>
  );
}

function AccuracyPct({ pct }: { pct: number }) {
  const color =
    pct >= 90
      ? "text-emerald-400"
      : pct >= 70
        ? "text-amber-400"
        : "text-red-400";
  return <span className={`font-bold tabular-nums ${color}`}>{pct}%</span>;
}

function MatchdayDetail({ entry }: { entry: AccuracyMatchdayRankingEntry }) {
  const actualPlayers = entry.players.filter((p) => p.in_actual);
  const optimalPlayers = entry.players.filter((p) => p.in_optimal);

  return (
    <div className="border-t border-vpv-border px-4 py-3">
      <div className="grid grid-cols-2 gap-4">
        {/* Actual XI */}
        <div>
          <p className="mb-1.5 text-[10px] font-semibold uppercase text-vpv-text-muted">
            Tu XI ({entry.formation_used}) — {entry.actual_points} pts
          </p>
          <div className="space-y-0.5">
            {actualPlayers
              .sort((a, b) => {
                const order = { POR: 0, DEF: 1, MED: 2, DEL: 3 };
                return (
                  (order[a.position as keyof typeof order] ?? 4) -
                  (order[b.position as keyof typeof order] ?? 4)
                );
              })
              .map((p) => (
                <div
                  key={p.player_id}
                  className={`flex items-center gap-1.5 text-[11px] ${
                    !p.in_optimal ? "text-red-400" : "text-vpv-text"
                  }`}
                >
                  <span
                    className={`w-6 text-[9px] font-bold ${POS_COLORS[p.position] ?? "text-vpv-text-muted"}`}
                  >
                    {p.position}
                  </span>
                  <span className="flex-1 truncate">{p.name}</span>
                  <span className="tabular-nums">{p.points}</span>
                </div>
              ))}
          </div>
        </div>

        {/* Optimal XI */}
        <div>
          <p className="mb-1.5 text-[10px] font-semibold uppercase text-vpv-text-muted">
            Mejor XI ({entry.optimal_formation}) — {entry.optimal_points} pts
          </p>
          <div className="space-y-0.5">
            {optimalPlayers
              .sort((a, b) => {
                const order = { POR: 0, DEF: 1, MED: 2, DEL: 3 };
                return (
                  (order[a.position as keyof typeof order] ?? 4) -
                  (order[b.position as keyof typeof order] ?? 4)
                );
              })
              .map((p) => (
                <div
                  key={p.player_id}
                  className={`flex items-center gap-1.5 text-[11px] ${
                    !p.in_actual ? "text-emerald-400" : "text-vpv-text"
                  }`}
                >
                  <span
                    className={`w-6 text-[9px] font-bold ${POS_COLORS[p.position] ?? "text-vpv-text-muted"}`}
                  >
                    {p.position}
                  </span>
                  <span className="flex-1 truncate">{p.name}</span>
                  <span className="tabular-nums">{p.points}</span>
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* Missed calls */}
      {entry.missed_calls.length > 0 && (
        <div className="mt-2 border-t border-vpv-border pt-2 space-y-0.5">
          <p className="text-[10px] font-semibold uppercase text-vpv-text-muted">
            Cambios que debiste hacer
          </p>
          {entry.missed_calls.map((mc, i) => (
            <div key={i} className="flex items-center gap-1.5 text-[11px]">
              <span className={`text-[9px] font-bold ${POS_COLORS[mc.position] ?? ""}`}>
                {mc.position}
              </span>
              <span className="text-red-400">
                {mc.lined_up_name} ({mc.lined_up_points})
              </span>
              <span className="text-vpv-text-muted">→</span>
              <span className="text-emerald-400">
                {mc.benched_name} ({mc.benched_points})
              </span>
              <span className="text-vpv-text-muted">
                +{mc.benched_points - mc.lined_up_points}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AciertoPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const [matchday, setMatchday] = useState<number | "">();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const queryParam = matchday ? `?matchday=${matchday}` : "";
  const { data, loading } = useFetch<AccuracyRankingResponse>(
    selectedSeason
      ? `/lineups/${selectedSeason.id}/accuracy/ranking${queryParam}`
      : null,
  );
  const { data: matchdays } = useFetch<MatchdayListResponse>(
    selectedSeason ? `/matchdays/${selectedSeason.id}` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-vpv-text">Acierto de Mister</h1>
        <SkeletonTable rows={8} />
      </div>
    );
  }

  const isMatchdayView = data?.matchday_entries && data.matchday_entries.length > 0;
  const globalEntries = data?.entries ?? [];
  const mdEntries = data?.matchday_entries ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-vpv-text">
            Acierto de Mister
          </h1>
          <p className="text-sm text-vpv-text-muted">
            Quien elige mejor su XI — {data?.season_name}
          </p>
        </div>

        {/* Matchday dropdown */}
        <select
          value={matchday ?? ""}
          onChange={(e) => {
            const val = e.target.value;
            setMatchday(val ? Number(val) : undefined);
            setExpandedId(null);
          }}
          className="rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text"
        >
          <option value="">Toda la temporada</option>
          {matchdays?.matchdays
            .filter((m) => m.stats_ok)
            .sort((a, b) => b.number - a.number)
            .map((m) => (
              <option key={m.number} value={m.number}>
                Jornada {m.number}
              </option>
            ))}
        </select>
      </div>

      {/* Global ranking view */}
      {!isMatchdayView && globalEntries.length > 0 && (
        <>
          {/* Desktop */}
          <div className="hidden md:block rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
                  <th className="px-4 py-2.5 w-12">#</th>
                  <th className="px-4 py-2.5">Mister</th>
                  <th className="px-4 py-2.5 w-48">Acierto</th>
                  <th className="px-4 py-2.5 text-right w-20">%</th>
                  <th className="px-4 py-2.5 text-right w-20">Perfectas</th>
                  <th className="px-4 py-2.5 text-right w-24">Pts perdidos</th>
                </tr>
              </thead>
              <tbody>
                {globalEntries.map((e) => (
                  <tr
                    key={e.participant_id}
                    className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                  >
                    <td className="px-4 py-2.5">
                      {RANK_BADGES[e.rank] ? (
                        <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${RANK_BADGES[e.rank]}`}>
                          {e.rank}
                        </span>
                      ) : (
                        <span className="text-vpv-text-muted">{e.rank}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-medium text-vpv-text">{e.display_name}</td>
                    <td className="px-4 py-2.5"><AccuracyBar pct={e.avg_accuracy} /></td>
                    <td className="px-4 py-2.5 text-right"><AccuracyPct pct={e.avg_accuracy} /></td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-vpv-text">{e.perfect_weeks}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-red-400">-{e.total_missed_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Mobile */}
          <div className="space-y-2 md:hidden">
            {globalEntries.map((e) => (
              <div key={e.participant_id} className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3">
                <div className="flex items-center gap-3 mb-2">
                  {RANK_BADGES[e.rank] ? (
                    <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${RANK_BADGES[e.rank]}`}>{e.rank}</span>
                  ) : (
                    <span className="inline-flex h-7 w-7 items-center justify-center text-sm text-vpv-text-muted">{e.rank}</span>
                  )}
                  <span className="flex-1 font-medium text-vpv-text">{e.display_name}</span>
                  <AccuracyPct pct={e.avg_accuracy} />
                </div>
                <AccuracyBar pct={e.avg_accuracy} />
                <div className="mt-2 flex gap-4 text-[11px] text-vpv-text-muted">
                  <span>Perfectas: {e.perfect_weeks}</span>
                  <span className="text-red-400">Perdidos: -{e.total_missed_points}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Matchday detail view */}
      {isMatchdayView && (
        <div className="space-y-2">
          {mdEntries.map((e) => {
            const isExpanded = expandedId === e.participant_id;
            return (
              <div
                key={e.participant_id}
                className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : e.participant_id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-vpv-bg/50"
                >
                  {RANK_BADGES[e.rank] ? (
                    <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${RANK_BADGES[e.rank]}`}>{e.rank}</span>
                  ) : (
                    <span className="inline-flex h-7 w-7 items-center justify-center text-sm text-vpv-text-muted">{e.rank}</span>
                  )}
                  <span className="flex-1 font-medium text-vpv-text">{e.display_name}</span>
                  <span className="text-xs tabular-nums text-vpv-text-muted">
                    {e.actual_points}/{e.optimal_points}
                  </span>
                  <AccuracyPct pct={e.accuracy_pct} />
                  <svg
                    width="14" height="14" viewBox="0 0 16 16" fill="none"
                    className={`text-vpv-text-muted transition-transform ${isExpanded ? "rotate-180" : ""}`}
                  >
                    <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>

                {isExpanded && <MatchdayDetail entry={e} />}
              </div>
            );
          })}
        </div>
      )}

      {!isMatchdayView && globalEntries.length === 0 && (
        <p className="text-vpv-text-muted">No hay datos disponibles.</p>
      )}
    </div>
  );
}
