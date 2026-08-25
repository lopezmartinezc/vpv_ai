"use client";

import { useState, useEffect, useMemo } from "react";
import { apiClient } from "@/lib/api-client";
import type {
  AdvancedPlayerStat,
  TeamDependencyEntry,
  ComparePlayerAxis,
  ComparePlayersResponse,
  PlayerSplit,
  PlayerSplitsResponse,
} from "@/types";

export function ContextoTab({
  seasonId,
  dependency,
  advancedPlayers,
  includeNoncounting = false,
}: {
  seasonId: number;
  dependency: TeamDependencyEntry[];
  advancedPlayers: AdvancedPlayerStat[];
  includeNoncounting?: boolean;
}) {
  // Compare state
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [compareData, setCompareData] = useState<ComparePlayerAxis[]>([]);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareSearch, setCompareSearch] = useState("");

  // Splits state
  const [splitPlayerId, setSplitPlayerId] = useState<number | null>(null);
  const [splits, setSplits] = useState<PlayerSplit[]>([]);
  const [splitPlayerName, setSplitPlayerName] = useState("");
  const [splitLoading, setSplitLoading] = useState(false);

  const filteredPlayers = useMemo(() => {
    if (!compareSearch.trim()) return [];
    const q = compareSearch.toLowerCase();
    return advancedPlayers
      .filter(
        (p) =>
          p.display_name.toLowerCase().includes(q) ||
          p.team_name.toLowerCase().includes(q),
      )
      .slice(0, 10);
  }, [advancedPlayers, compareSearch]);

  const addCompare = (id: number) => {
    if (compareIds.length < 3 && !compareIds.includes(id)) {
      setCompareIds((prev) => [...prev, id]);
    }
    setCompareSearch("");
  };

  const removeCompare = (id: number) => {
    setCompareIds((prev) => prev.filter((x) => x !== id));
    setCompareData((prev) => prev.filter((p) => p.player_id !== id));
  };

  // Fetch comparison when IDs change (2+ selected)
  useEffect(() => {
    if (compareIds.length < 2) {
      /* eslint-disable-next-line react-hooks/set-state-in-effect -- clearing stale data when selection drops below threshold */
      setCompareData([]);
      return;
    }
    let cancelled = false;
    setCompareLoading(true);
    apiClient
      .get<ComparePlayersResponse>(
        `/stats/${seasonId}/players/compare?player_ids=${compareIds.join(",")}${
          includeNoncounting ? "&include_noncounting=true" : ""
        }`,
      )
      .then((data) => {
        if (!cancelled) setCompareData(data.players);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setCompareLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [seasonId, compareIds, includeNoncounting]);

  // Fetch splits
  const fetchSplits = (playerId: number, name: string) => {
    setSplitPlayerId(playerId);
    setSplitPlayerName(name);
    setSplitLoading(true);
    apiClient
      .get<PlayerSplitsResponse>(
        `/stats/${seasonId}/players/${playerId}/splits${
          includeNoncounting ? "?include_noncounting=true" : ""
        }`,
      )
      .then((data) => setSplits(data.splits))
      .catch(() => setSplits([]))
      .finally(() => setSplitLoading(false));
  };

  return (
    <div className="space-y-6">
      {/* Team Dependency */}
      <div className="rounded-lg border border-vpv-border bg-vpv-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-vpv-text">
          Dependencia de Equipo
        </h3>
        <p className="mb-3 text-xs text-vpv-text-muted">
          % de puntos fantasy del equipo que aporta un solo jugador
        </p>
        {dependency.length === 0 ? (
          <p className="text-sm text-vpv-text-muted">Sin datos</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vpv-border text-left text-xs text-vpv-text-muted">
                  <th className="px-2 py-1.5">Equipo</th>
                  <th className="px-2 py-1.5">Jugador Top</th>
                  <th className="px-2 py-1.5 text-right">Pts Jugador</th>
                  <th className="px-2 py-1.5 text-right">Pts Equipo</th>
                  <th className="px-2 py-1.5 text-right">Dependencia</th>
                </tr>
              </thead>
              <tbody>
                {dependency.map((d) => (
                  <tr
                    key={d.team_name}
                    className="border-b border-vpv-border/50 last:border-0 hover:bg-vpv-bg/50"
                  >
                    <td className="px-2 py-1.5 font-medium text-vpv-text">
                      {d.team_name}
                    </td>
                    <td
                      className="cursor-pointer px-2 py-1.5 text-vpv-accent hover:underline"
                      onClick={() =>
                        fetchSplits(d.top_player_id, d.top_player_name)
                      }
                    >
                      {d.top_player_name}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                      {d.top_player_points}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                      {d.team_total_points}
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      <span
                        className={`tabular-nums font-medium ${
                          d.dependency_pct > 20
                            ? "text-red-400"
                            : d.dependency_pct > 15
                              ? "text-amber-400"
                              : "text-green-400"
                        }`}
                      >
                        {d.dependency_pct.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Player Splits */}
      {splitPlayerId && (
        <div className="rounded-lg border border-vpv-border bg-vpv-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-vpv-text">
              Splits: {splitPlayerName}
            </h3>
            <button
              onClick={() => setSplitPlayerId(null)}
              className="text-xs text-vpv-text-muted hover:text-vpv-text"
            >
              Cerrar
            </button>
          </div>
          {splitLoading ? (
            <div className="h-8 animate-pulse rounded bg-vpv-border" />
          ) : splits.length === 0 ? (
            <p className="text-sm text-vpv-text-muted">Sin datos de splits</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {splits.map((s) => (
                <div
                  key={s.location}
                  className={`rounded-lg border p-3 ${
                    s.location === "home"
                      ? "border-blue-500/30 bg-blue-500/10"
                      : "border-amber-500/30 bg-amber-500/10"
                  }`}
                >
                  <div className="mb-2 text-xs font-semibold uppercase text-vpv-text-muted">
                    {s.location === "home" ? "Local" : "Visitante"}
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-xs">
                    <span className="text-vpv-text-muted">Partidos</span>
                    <span className="text-right tabular-nums text-vpv-text">
                      {s.matches}
                    </span>
                    <span className="text-vpv-text-muted">Media pts</span>
                    <span className="text-right tabular-nums font-medium text-vpv-accent">
                      {s.avg_points.toFixed(1)}
                    </span>
                    <span className="text-vpv-text-muted">Total pts</span>
                    <span className="text-right tabular-nums text-vpv-text">
                      {s.total_points}
                    </span>
                    <span className="text-vpv-text-muted">Goles</span>
                    <span className="text-right tabular-nums text-vpv-text">
                      {s.goals}
                    </span>
                    <span className="text-vpv-text-muted">Asistencias</span>
                    <span className="text-right tabular-nums text-vpv-text">
                      {s.assists}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Player Comparison Radar */}
      <div className="rounded-lg border border-vpv-border bg-vpv-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-vpv-text">
          Comparar Jugadores (max 3)
        </h3>

        {/* Selected players */}
        <div className="mb-3 flex flex-wrap gap-2">
          {compareIds.map((id) => {
            const p = advancedPlayers.find((ap) => ap.player_id === id);
            return (
              <span
                key={id}
                className="inline-flex items-center gap-1 rounded bg-vpv-accent/20 px-2 py-1 text-xs text-vpv-accent"
              >
                {p?.display_name ?? `#${id}`}
                <button
                  onClick={() => removeCompare(id)}
                  className="ml-1 text-vpv-text-muted hover:text-red-400"
                >
                  &times;
                </button>
              </span>
            );
          })}
        </div>

        {/* Search to add */}
        {compareIds.length < 3 && (
          <div className="relative mb-3">
            <input
              type="text"
              value={compareSearch}
              onChange={(e) => setCompareSearch(e.target.value)}
              placeholder="Buscar jugador para comparar..."
              className="w-full rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text placeholder:text-vpv-text-muted"
            />
            {filteredPlayers.length > 0 && (
              <div className="absolute z-20 mt-1 max-h-40 w-full overflow-y-auto rounded border border-vpv-border bg-vpv-card shadow-lg">
                {filteredPlayers.map((p) => (
                  <button
                    key={p.player_id}
                    onClick={() => addCompare(p.player_id)}
                    className="flex w-full items-center justify-between px-3 py-1.5 text-left text-sm hover:bg-vpv-bg"
                  >
                    <span className="text-vpv-text">{p.display_name}</span>
                    <span className="text-xs text-vpv-text-muted">
                      {p.position} — {p.team_name}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Radar chart */}
        {compareLoading ? (
          <div className="h-40 animate-pulse rounded bg-vpv-border" />
        ) : compareData.length >= 2 ? (
          <RadarChart players={compareData} />
        ) : (
          <p className="py-4 text-center text-xs text-vpv-text-muted">
            Selecciona al menos 2 jugadores para comparar
          </p>
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-vpv-text-muted">
        <span>Dependencia = % puntos equipo de un jugador</span>
        <span>Splits = rendimiento local vs visitante</span>
        <span>Radar: 6 ejes normalizados 0-100 entre los comparados</span>
      </div>
    </div>
  );
}

/** SVG radar chart for player comparison. */
const RADAR_AXES = [
  { key: "goals_rate", label: "Goles" },
  { key: "assists_rate", label: "Asist." },
  { key: "avg_points", label: "Media" },
  { key: "consistency", label: "Consist." },
  { key: "pp90", label: "pp90" },
  { key: "form", label: "Forma" },
] as const;

const RADAR_COLORS = ["#60a5fa", "#f97316", "#34d399"];

function RadarChart({ players }: { players: ComparePlayerAxis[] }) {
  const cx = 150;
  const cy = 150;
  const r = 120;
  const levels = 5;
  const n = RADAR_AXES.length;
  const angleStep = (2 * Math.PI) / n;

  const getPoint = (angle: number, value: number) => ({
    x: cx + (r * value) / 100 * Math.cos(angle - Math.PI / 2),
    y: cy + (r * value) / 100 * Math.sin(angle - Math.PI / 2),
  });

  return (
    <div className="flex flex-col items-center gap-3">
      <svg width={300} height={300} viewBox="0 0 300 300" className="max-w-full">
        {/* Grid */}
        {Array.from({ length: levels }, (_, i) => {
          const lvl = ((i + 1) / levels) * 100;
          const points = Array.from({ length: n }, (_, j) => {
            const p = getPoint(j * angleStep, lvl);
            return `${p.x},${p.y}`;
          }).join(" ");
          return (
            <polygon
              key={i}
              points={points}
              fill="none"
              stroke="currentColor"
              strokeWidth={0.5}
              className="text-vpv-border"
            />
          );
        })}

        {/* Axes */}
        {RADAR_AXES.map((_, i) => {
          const p = getPoint(i * angleStep, 100);
          return (
            <line
              key={i}
              x1={cx}
              y1={cy}
              x2={p.x}
              y2={p.y}
              stroke="currentColor"
              strokeWidth={0.5}
              className="text-vpv-border"
            />
          );
        })}

        {/* Labels */}
        {RADAR_AXES.map((ax, i) => {
          const p = getPoint(i * angleStep, 115);
          return (
            <text
              key={ax.key}
              x={p.x}
              y={p.y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-current text-[10px] text-vpv-text-muted"
            >
              {ax.label}
            </text>
          );
        })}

        {/* Player polygons */}
        {players.map((player, pi) => {
          const points = RADAR_AXES.map((ax, i) => {
            const val = player[ax.key as keyof ComparePlayerAxis] as number;
            const p = getPoint(i * angleStep, val);
            return `${p.x},${p.y}`;
          }).join(" ");
          return (
            <polygon
              key={player.player_id}
              points={points}
              fill={RADAR_COLORS[pi]}
              fillOpacity={0.15}
              stroke={RADAR_COLORS[pi]}
              strokeWidth={2}
            />
          );
        })}

        {/* Player dots */}
        {players.map((player, pi) =>
          RADAR_AXES.map((ax, i) => {
            const val = player[ax.key as keyof ComparePlayerAxis] as number;
            const p = getPoint(i * angleStep, val);
            return (
              <circle
                key={`${player.player_id}-${ax.key}`}
                cx={p.x}
                cy={p.y}
                r={3}
                fill={RADAR_COLORS[pi]}
              >
                <title>
                  {player.display_name}: {ax.label} = {val.toFixed(0)}
                </title>
              </circle>
            );
          }),
        )}
      </svg>

      {/* Legend */}
      <div className="flex gap-4">
        {players.map((p, i) => (
          <div key={p.player_id} className="flex items-center gap-1.5 text-xs">
            <div
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: RADAR_COLORS[i] }}
            />
            <span className="text-vpv-text">{p.display_name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Draft Value Tab
// ---------------------------------------------------------------------------
