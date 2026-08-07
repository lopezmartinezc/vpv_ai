"use client";

import { useState, useMemo } from "react";
import { sorted, SortDir, POS_COLOR } from "@/components/admin/stats/common";
import type {
  AdvancedPlayerStat,
} from "@/types";

const ADV_POS_FILTERS = ["Todos", "POR", "DEF", "MED", "DEL"] as const;

type AdvSortKey = keyof AdvancedPlayerStat;

function TrendIcon({ trend }: { trend: "rising" | "stable" | "falling" }) {
  if (trend === "rising")
    return <span className="text-green-400" title="Tendencia al alza">&#9650;</span>;
  if (trend === "falling")
    return <span className="text-red-400" title="Tendencia a la baja">&#9660;</span>;
  return <span className="text-vpv-text-muted" title="Estable">&#9654;</span>;
}

function CvBadge({ cv }: { cv: number }) {
  const color =
    cv < 0.3
      ? "text-green-400"
      : cv < 0.5
        ? "text-amber-400"
        : "text-red-400";
  return <span className={`tabular-nums ${color}`}>{cv.toFixed(2)}</span>;
}

export function AdvancedTab({ players }: { players: AdvancedPlayerStat[] }) {
  const [posFilter, setPosFilter] = useState<string>("Todos");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<AdvSortKey>("total_points");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (key: AdvSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const filtered = useMemo(() => {
    let list = players;
    if (posFilter !== "Todos") {
      list = list.filter((p) => p.position === posFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          p.display_name.toLowerCase().includes(q) ||
          p.team_name.toLowerCase().includes(q),
      );
    }
    return sorted(list, sortKey, sortDir);
  }, [players, posFilter, search, sortKey, sortDir]);

  const cols: { key: AdvSortKey; label: string; short: string; title: string }[] = [
    { key: "matchdays_played", label: "PJ", short: "PJ", title: "Partidos jugados" },
    { key: "avg_points", label: "PPM", short: "PPM", title: "Puntos por partido" },
    { key: "std_dev", label: "σ", short: "σ", title: "Desviacion estandar" },
    { key: "cv", label: "CV", short: "CV", title: "Coef. variacion (menor = mas consistente)" },
    { key: "p10", label: "P10", short: "P10", title: "Percentil 10 (peor caso)" },
    { key: "p50", label: "P50", short: "P50", title: "Mediana" },
    { key: "p90", label: "P90", short: "P90", title: "Percentil 90 (mejor caso)" },
    { key: "pp90", label: "pp90", short: "pp90", title: "Puntos por 90 minutos" },
    { key: "ci_lower", label: "CI-", short: "CI-", title: "Intervalo confianza 95% (inferior)" },
    { key: "ci_upper", label: "CI+", short: "CI+", title: "Intervalo confianza 95% (superior)" },
    { key: "form_5", label: "Form", short: "Form", title: "Media ponderada ultimos 5 partidos" },
    { key: "total_points", label: "Total", short: "Tot", title: "Puntos totales" },
  ];

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {ADV_POS_FILTERS.map((pos) => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                posFilter === pos
                  ? "bg-vpv-accent text-white"
                  : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {pos}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Buscar jugador o equipo..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text placeholder:text-vpv-text-muted"
        />
        <span className="text-xs text-vpv-text-muted">
          {filtered.length} jugadores
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-vpv-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card">
              <th className="sticky left-0 z-10 bg-vpv-card px-3 py-2 text-left text-xs font-semibold uppercase text-vpv-text-muted">
                Jugador
              </th>
              <th className="px-2 py-2 text-left text-xs font-semibold uppercase text-vpv-text-muted">
                Pos
              </th>
              {cols.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  title={col.title}
                  className="cursor-pointer px-2 py-2 text-right text-xs font-semibold uppercase text-vpv-text-muted hover:text-vpv-text"
                >
                  {col.short}
                  {sortKey === col.key && (
                    <span className="ml-0.5">
                      {sortDir === "asc" ? "▲" : "▼"}
                    </span>
                  )}
                </th>
              ))}
              <th className="px-2 py-2 text-center text-xs font-semibold uppercase text-vpv-text-muted">
                Trend
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <tr
                key={p.player_id}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
              >
                <td className="sticky left-0 z-10 bg-vpv-bg px-3 py-1.5">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium text-vpv-text" title={p.display_name}>
                      {p.display_name}
                    </span>
                    <span className="hidden truncate text-xs text-vpv-text-muted sm:inline">
                      {p.team_name}
                    </span>
                  </div>
                </td>
                <td className="px-2 py-1.5">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POS_COLOR[p.position] ?? ""}`}
                  >
                    {p.position}
                  </span>
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                  {p.matchdays_played}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums font-medium text-vpv-accent">
                  {p.avg_points.toFixed(1)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                  {p.std_dev.toFixed(1)}
                </td>
                <td className="px-2 py-1.5 text-right">
                  <CvBadge cv={p.cv} />
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-red-400">
                  {p.p10.toFixed(0)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text">
                  {p.p50.toFixed(0)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-green-400">
                  {p.p90.toFixed(0)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                  {p.pp90.toFixed(1)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                  {p.ci_lower.toFixed(1)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                  {p.ci_upper.toFixed(1)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text">
                  {p.form_5 !== null ? p.form_5.toFixed(1) : "—"}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums font-medium text-vpv-text">
                  {p.total_points}
                </td>
                <td className="px-2 py-1.5 text-center">
                  <TrendIcon trend={p.trend} />
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={cols.length + 3}
                  className="px-4 py-6 text-center text-vpv-text-muted"
                >
                  Sin resultados
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-vpv-text-muted">
        <span>PPM = puntos/partido</span>
        <span>σ = desviacion estandar</span>
        <span>CV = coef. variacion</span>
        <span>P10/P50/P90 = percentiles</span>
        <span>pp90 = puntos por 90 min</span>
        <span>CI = intervalo confianza 95%</span>
        <span>Form = media ponderada ultimos 5</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Contexto Tab (Phase 4)
// ---------------------------------------------------------------------------
