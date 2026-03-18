"use client";

import { useMemo, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { PredictionsResponse, PlayerPrediction } from "@/types";

const POS_COLORS: Record<string, string> = {
  POR: "bg-amber-600/20 text-amber-400",
  DEF: "bg-blue-600/20 text-blue-400",
  MED: "bg-green-600/20 text-green-400",
  DEL: "bg-red-600/20 text-red-400",
};

const CONF_COLORS: Record<string, string> = {
  alta: "text-green-400",
  media: "text-amber-400",
  baja: "text-red-400",
};

const TREND_ICONS: Record<string, { icon: string; color: string }> = {
  rising: { icon: "\u2191", color: "text-green-400" },
  stable: { icon: "\u2192", color: "text-vpv-text-muted" },
  falling: { icon: "\u2193", color: "text-red-400" },
};

const DIFF_COLORS: Record<string, string> = {
  facil: "border-green-500/40 bg-green-500/10 text-green-400",
  medio: "border-amber-500/40 bg-amber-500/10 text-amber-400",
  dificil: "border-red-500/40 bg-red-500/10 text-red-400",
};

type SortKey = "xpts" | "season_avg" | "form_5" | "rival_factor" | "confidence" | "player_name";

export default function PrediccionesPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const mdCurrent = selectedSeason?.matchday_current ?? null;

  const { data, loading } = useFetch<PredictionsResponse>(
    selectedSeason && mdCurrent
      ? `/stats/${selectedSeason.id}/predictions?matchday=${mdCurrent}`
      : null,
  );

  const [filterPosition, setFilterPosition] = useState<string | null>(null);
  const [filterTeam, setFilterTeam] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("xpts");
  const [sortAsc, setSortAsc] = useState(false);

  const teams = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.predictions.map((p) => p.team_name))].sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase().trim();
    return data.predictions
      .filter((p) => {
        if (filterPosition && p.position !== filterPosition) return false;
        if (filterTeam && p.team_name !== filterTeam) return false;
        if (q && !p.player_name.toLowerCase().includes(q)) return false;
        return true;
      })
      .sort((a, b) => {
        const av = getSortValue(a, sortKey);
        const bv = getSortValue(b, sortKey);
        return sortAsc ? av - bv : bv - av;
      });
  }, [data, filterPosition, filterTeam, search, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-60 animate-pulse rounded bg-vpv-border" />
        <div className="h-64 animate-pulse rounded-lg bg-vpv-border" />
      </div>
    );
  }

  if (!data || data.predictions.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-vpv-text">
          Predicciones J{mdCurrent}
        </h2>
        <p className="py-10 text-center text-vpv-text-muted">
          No hay datos para generar predicciones.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-vpv-text">
        Predicciones J{data.matchday_number}
      </h2>

      {/* Opponent difficulty */}
      {data.opponent_rankings.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
            Dificultad rival
          </p>
          <div className="flex flex-wrap gap-2">
            {data.opponent_rankings.map((o) => (
              <div
                key={o.team_name}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${DIFF_COLORS[o.difficulty] ?? ""}`}
              >
                {o.team_name}
                <span className="ml-1.5 opacity-70">
                  {o.goals_conceded_avg.toFixed(1)} goles/p
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="Buscar jugador..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-vpv-border bg-vpv-card px-3 py-2 text-sm text-vpv-text placeholder:text-vpv-text-muted/50 focus:border-vpv-accent focus:outline-none sm:w-48"
        />
        <select
          value={filterPosition ?? ""}
          onChange={(e) => setFilterPosition(e.target.value || null)}
          className="rounded-lg border border-vpv-border bg-vpv-card px-3 py-2 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
        >
          <option value="">Posicion</option>
          {["POR", "DEF", "MED", "DEL"].map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <select
          value={filterTeam ?? ""}
          onChange={(e) => setFilterTeam(e.target.value || null)}
          className="rounded-lg border border-vpv-border bg-vpv-card px-3 py-2 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
        >
          <option value="">Equipo</option>
          {teams.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <span className="self-center text-xs text-vpv-text-muted">
          {filtered.length} jugadores
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-xs text-vpv-text-muted">
              <th className="px-3 py-2.5">Jugador</th>
              <th className="w-10 px-2 py-2.5 text-center" title="Posicion del jugador">Pos</th>
              <th className="px-2 py-2.5" title="Equipo rival en esta jornada">Rival</th>
              <TipHeader label="C/F" tip="Casa (C) o Fuera (F). Jugar en casa suele dar mas puntos." />
              <SortHeader label="Media" sortKey="season_avg" current={sortKey} asc={sortAsc} onToggle={toggleSort} tip="Media de puntos en toda la temporada (20% del xPts)" />
              <SortHeader label="Forma" sortKey="form_5" current={sortKey} asc={sortAsc} onToggle={toggleSort} tip="EWMA ultimos 5 partidos: da mas peso a los recientes (40% del xPts)" />
              <SortHeader label="xPts" sortKey="xpts" current={sortKey} asc={sortAsc} onToggle={toggleSort} tip="Puntos esperados = Forma (40%) + Media (20%) + Factor rival (25%) + Casa/Fuera (15%), ajustado por probabilidad de titular" />
              <TipHeader label="Rango" tip="Floor - Ceiling: xPts +/- desviacion estandar. Rango probable de puntos." />
              <TipHeader label="Titular" tip="% de partidos recientes (ultimos 5) donde fue titular (>= 45 min). P = lanzador de penaltis." />
              <TipHeader label="Conf" tip="Confianza en la prediccion. Alta: baja variabilidad + 10+ partidos. Baja: pocos datos o muy irregular." />
              <TipHeader label="PJ" tip="Partidos jugados esta temporada. Mas partidos = datos mas fiables." />
              <TipHeader label="Trend" tip="Tendencia: subiendo si forma > 110% de media, bajando si < 90%." />
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => {
              const trend = TREND_ICONS[p.trend] ?? TREND_ICONS.stable;
              return (
                <tr
                  key={p.player_id}
                  className="border-b border-vpv-border last:border-0 hover:bg-vpv-accent/5"
                >
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <PlayerAvatar photoPath={p.photo_path} name={p.player_name} size={28} />
                      <div className="min-w-0">
                        <span className="block truncate font-medium text-vpv-text">
                          {p.player_name}
                        </span>
                        <span className="text-[10px] text-vpv-text-muted">
                          {p.team_name}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="px-2 py-2 text-center">
                    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold ${POS_COLORS[p.position] ?? ""}`}>
                      {p.position}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-xs text-vpv-text-muted">
                    {p.opponent_name}
                  </td>
                  <td className="px-2 py-2 text-center text-xs">
                    {p.is_home ? (
                      <span className="text-green-400">C</span>
                    ) : (
                      <span className="text-vpv-text-muted">F</span>
                    )}
                  </td>
                  <td className="px-2 py-2 text-center tabular-nums text-vpv-text-muted">
                    {p.season_avg.toFixed(1)}
                  </td>
                  <td className="px-2 py-2 text-center tabular-nums text-vpv-text">
                    {p.form_5 != null ? p.form_5.toFixed(1) : "-"}
                  </td>
                  <td className="px-2 py-2 text-center font-bold tabular-nums text-vpv-accent">
                    {p.xpts.toFixed(1)}
                  </td>
                  <td className="px-2 py-2 text-center text-[10px] tabular-nums text-vpv-text-muted">
                    {p.xpts_floor.toFixed(0)}-{p.xpts_ceiling.toFixed(0)}
                  </td>
                  <td className="px-2 py-2 text-center">
                    <span className={`text-xs tabular-nums font-medium ${
                      p.starter_pct >= 80 ? "text-green-400" : p.starter_pct >= 40 ? "text-amber-400" : "text-red-400"
                    }`}>
                      {p.starter_pct.toFixed(0)}%
                    </span>
                    {p.is_penalty_taker && (
                      <span className="ml-0.5 text-[9px] text-vpv-accent" title="Lanzador de penaltis">P</span>
                    )}
                  </td>
                  <td className={`px-2 py-2 text-center text-xs font-medium ${CONF_COLORS[p.confidence] ?? ""}`}>
                    {p.confidence}
                  </td>
                  <td className="px-2 py-2 text-center text-xs tabular-nums text-vpv-text-muted">
                    {p.matchdays_played}
                  </td>
                  <td className={`px-2 py-2 text-center font-bold ${trend.color}`}>
                    {trend.icon}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TipHeader({ label, tip }: { label: string; tip: string }) {
  return (
    <th className="px-2 py-2.5 text-center" title={tip}>
      <span className="cursor-help border-b border-dashed border-vpv-text-muted/30 text-xs font-medium text-vpv-text-muted">
        {label}
      </span>
    </th>
  );
}

function SortHeader({
  label,
  sortKey,
  current,
  asc,
  onToggle,
  tip,
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  asc: boolean;
  onToggle: (key: SortKey) => void;
  tip?: string;
}) {
  const active = current === sortKey;
  return (
    <th className="px-2 py-2.5 text-center" title={tip}>
      <button
        onClick={() => onToggle(sortKey)}
        className={`cursor-help border-b border-dashed border-vpv-text-muted/30 text-xs font-medium ${active ? "text-vpv-accent" : "text-vpv-text-muted hover:text-vpv-text"}`}
      >
        {label}
        {active && (
          <span className="ml-0.5">{asc ? "\u25B2" : "\u25BC"}</span>
        )}
      </button>
    </th>
  );
}

function getSortValue(p: PlayerPrediction, key: SortKey): number {
  switch (key) {
    case "xpts": return p.xpts;
    case "season_avg": return p.season_avg;
    case "form_5": return p.form_5 ?? 0;
    case "rival_factor": return p.rival_factor;
    case "confidence": return p.confidence === "alta" ? 3 : p.confidence === "media" ? 2 : 1;
    case "player_name": return 0; // handled separately if needed
  }
}
