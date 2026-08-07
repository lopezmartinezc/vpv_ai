"use client";

import { useState, useMemo } from "react";
import { sorted, SortDir, POS_COLOR } from "@/components/admin/stats/common";
import type {
  PlayerStatRow,
} from "@/types";

const POS_FILTERS = ["Todos", "POR", "DEF", "MED", "DEL"] as const;

/**
 * PlayersTab — Sortable table of per-player season stats.
 * Features: position filter chips, text search (name/team), top stats cards,
 * responsive column headers (full label on desktop, abbreviation on mobile).
 */
export function PlayersTab({ players }: { players: PlayerStatRow[] }) {
  const [sortKey, setSortKey] = useState<keyof PlayerStatRow>("total_points");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [posFilter, setPosFilter] = useState<string>("Todos");
  const [search, setSearch] = useState("");

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

  function handleSort(key: keyof PlayerStatRow) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "display_name" || key === "team_name" ? "asc" : "desc");
    }
  }

  // Top stats cards
  const topScorer = useMemo(
    () =>
      players.length > 0
        ? [...players].sort((a, b) => b.goals - a.goals)[0]
        : null,
    [players],
  );
  const topAssister = useMemo(
    () =>
      players.length > 0
        ? [...players].sort((a, b) => b.assists - a.assists)[0]
        : null,
    [players],
  );
  const topAvg = useMemo(
    () =>
      players.filter((p) => p.matchdays_played >= 3).length > 0
        ? [...players]
            .filter((p) => p.matchdays_played >= 3)
            .sort((a, b) => b.avg_points - a.avg_points)[0]
        : null,
    [players],
  );
  const topPoints = useMemo(
    () =>
      players.length > 0
        ? [...players].sort((a, b) => b.total_points - a.total_points)[0]
        : null,
    [players],
  );

  type ColDef = {
    key: keyof PlayerStatRow;
    label: string;
    short: string;
    render?: (p: PlayerStatRow) => React.ReactNode;
  };

  const columns: ColDef[] = [
    { key: "display_name", label: "Jugador", short: "Jugador" },
    {
      key: "position",
      label: "Pos",
      short: "Pos",
      render: (p) => (
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-medium ${POS_COLOR[p.position] ?? "bg-vpv-bg text-vpv-text-muted"}`}
        >
          {p.position}
        </span>
      ),
    },
    { key: "team_name", label: "Equipo", short: "Eq" },
    { key: "matchdays_played", label: "PJ", short: "PJ" },
    { key: "started_count", label: "Titular", short: "TI" },
    { key: "goals", label: "Goles", short: "G" },
    { key: "penalty_goals", label: "G.Pen", short: "GP" },
    { key: "own_goals", label: "PP", short: "PP" },
    { key: "assists", label: "Asist.", short: "A" },
    { key: "penalties_saved", label: "P.Parad", short: "PS" },
    {
      key: "yellow_cards",
      label: "TA",
      short: "TA",
      render: (p) => <span className="text-yellow-400">{p.yellow_cards}</span>,
    },
    {
      key: "red_cards",
      label: "TR",
      short: "TR",
      render: (p) => <span className="text-red-400">{p.red_cards}</span>,
    },
    {
      key: "avg_marca",
      label: "Marca",
      short: "MR",
      render: (p) => (p.avg_marca !== null ? p.avg_marca.toFixed(1) : "\u2014"),
    },
    {
      key: "avg_as",
      label: "AS",
      short: "AS",
      render: (p) => (p.avg_as !== null ? p.avg_as.toFixed(1) : "\u2014"),
    },
    { key: "minutes_played", label: "Min", short: "Min" },
    {
      key: "avg_points",
      label: "Media",
      short: "Med",
      render: (p) => (
        <span className="text-vpv-text">{p.avg_points.toFixed(1)}</span>
      ),
    },
    {
      key: "total_points",
      label: "Puntos",
      short: "Pts",
      render: (p) => (
        <span className="font-medium text-vpv-accent">{p.total_points}</span>
      ),
    },
  ];

  const isTextCol = (key: string) =>
    key === "display_name" || key === "team_name" || key === "position";

  return (
    <div className="space-y-3">
      {/* Top stats cards */}
      {players.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              title: "Maximo goleador",
              player: topScorer,
              stat: topScorer ? `${topScorer.goals} goles` : "",
            },
            {
              title: "Maximo asistente",
              player: topAssister,
              stat: topAssister ? `${topAssister.assists} asist.` : "",
            },
            {
              title: "Mejor media (3+ PJ)",
              player: topAvg,
              stat: topAvg ? `${topAvg.avg_points.toFixed(1)} pts/j` : "",
            },
            {
              title: "Mas puntos total",
              player: topPoints,
              stat: topPoints ? `${topPoints.total_points} pts` : "",
            },
          ].map(
            (card) =>
              card.player && (
                <div
                  key={card.title}
                  className="rounded-lg border border-vpv-card-border bg-vpv-card p-3"
                >
                  <p className="text-xs text-vpv-text-muted">{card.title}</p>
                  <p className="font-semibold text-vpv-text">
                    {card.player.display_name}
                  </p>
                  <p className="text-sm text-vpv-accent">{card.stat}</p>
                  <p className="text-xs text-vpv-text-muted">
                    {card.player.team_name}
                  </p>
                </div>
              ),
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {POS_FILTERS.map((pos) => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                posFilter === pos
                  ? "bg-vpv-accent text-white"
                  : "bg-vpv-bg text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {pos}
            </button>
          ))}
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar jugador o equipo..."
          className="rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text placeholder:text-vpv-text-muted"
        />
        <span className="text-xs text-vpv-text-muted">
          {filtered.length} jugadores
        </span>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-vpv-border bg-vpv-bg text-left text-xs text-vpv-text-muted">
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={`cursor-pointer whitespace-nowrap px-2 py-2 hover:text-vpv-text ${!isTextCol(col.key) ? "text-right" : ""}`}
                    onClick={() => handleSort(col.key)}
                  >
                    <span className="hidden sm:inline">{col.label}</span>
                    <span className="sm:hidden">{col.short}</span>
                    {sortKey === col.key && (
                      <span className="ml-0.5">
                        {sortDir === "asc" ? "\u25B2" : "\u25BC"}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr
                  key={`${p.player_id}-${p.position}`}
                  className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`whitespace-nowrap px-2 py-1.5 ${!isTextCol(col.key) ? "text-right" : ""} ${col.key === "display_name" ? "font-medium text-vpv-text" : "text-vpv-text-muted"}`}
                    >
                      {col.render
                        ? col.render(p)
                        : (p[col.key] as React.ReactNode)}
                    </td>
                  ))}
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="px-4 py-6 text-center text-sm text-vpv-text-muted"
                  >
                    Sin resultados
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Participants Tab
// ---------------------------------------------------------------------------

/**
 * ParticipantsTab — Three sub-views:
 *  - Desglose:   Point breakdown table by scoring category per participant
 *  - Extremos:   Best/worst matchday + season average per participant
 *  - Evolucion:  Cumulative points matrix (matchdays as rows, participants as columns)
 */
