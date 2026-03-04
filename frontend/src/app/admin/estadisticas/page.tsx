/**
 * Admin Statistics Page — /admin/estadisticas
 *
 * Advanced analytics dashboard with three sub-tabs:
 *  - Jugadores:      Per-player aggregated stats (sortable table, position filters, search)
 *  - Participantes:  Point breakdown, best/worst matchdays, cumulative evolution
 *  - Liga:           Formation usage, most-lined-up players, matchday averages, records
 *
 * Data is fetched per-tab from three backend endpoints:
 *  GET /api/stats/{seasonId}/players
 *  GET /api/stats/{seasonId}/participants
 *  GET /api/stats/{seasonId}/league
 */
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api-client";
import type {
  PlayerStatRow,
  PlayerStatsResponse,
  ParticipantBreakdown,
  ParticipantExtremes,
  EvolutionEntry,
  ParticipantStatsResponse,
  FormationUsage,
  MostLinedUpPlayer,
  MatchdayAverageEntry,
  RecordEntry,
  LeagueStatsResponse,
} from "@/types";

// ---------------------------------------------------------------------------
// Sub-tabs
// ---------------------------------------------------------------------------

const STAT_TABS = [
  { key: "jugadores", label: "Jugadores" },
  { key: "participantes", label: "Participantes" },
  { key: "liga", label: "Liga" },
] as const;

type StatTab = (typeof STAT_TABS)[number]["key"];

// ---------------------------------------------------------------------------
// Sort helpers
// ---------------------------------------------------------------------------

type SortDir = "asc" | "desc";

/** Generic client-side sort — null/undefined values are pushed to the end. */
function sorted<T>(items: T[], key: keyof T, dir: SortDir): T[] {
  return [...items].sort((a, b) => {
    const va = a[key];
    const vb = b[key];
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    if (va < vb) return dir === "asc" ? -1 : 1;
    if (va > vb) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

interface SeasonOption {
  id: number;
  name: string;
  status: string;
}

/** Position badge colors — consistent with other admin tables. */
const POS_COLOR: Record<string, string> = {
  POR: "bg-amber-500/20 text-amber-400",
  DEF: "bg-blue-500/20 text-blue-400",
  MED: "bg-emerald-500/20 text-emerald-400",
  DEL: "bg-rose-500/20 text-rose-400",
};

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
      <p className="text-sm text-red-400">{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player Stats Tab
// ---------------------------------------------------------------------------

const POS_FILTERS = ["Todos", "POR", "DEF", "MED", "DEL"] as const;

/**
 * PlayersTab — Sortable table of per-player season stats.
 * Features: position filter chips, text search (name/team), top stats cards,
 * responsive column headers (full label on desktop, abbreviation on mobile).
 */
function PlayersTab({ players }: { players: PlayerStatRow[] }) {
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
function ParticipantsTab({
  breakdowns,
  extremes,
  evolution,
}: {
  breakdowns: ParticipantBreakdown[];
  extremes: ParticipantExtremes[];
  evolution: EvolutionEntry[];
}) {
  const [view, setView] = useState<"breakdown" | "extremes" | "evolution">(
    "breakdown",
  );

  return (
    <div className="space-y-3">
      <div className="flex gap-1">
        {(
          [
            { key: "breakdown", label: "Desglose" },
            { key: "extremes", label: "Extremos" },
            { key: "evolution", label: "Evolucion" },
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
      {view === "evolution" && <EvolutionTable evolution={evolution} />}
    </div>
  );
}

function BreakdownTable({
  breakdowns,
}: {
  breakdowns: ParticipantBreakdown[];
}) {
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

/** Cumulative evolution matrix — sticky first column for matchday label. */
function EvolutionTable({ evolution }: { evolution: EvolutionEntry[] }) {
  const matchdays = useMemo(() => {
    const map = new Map<number, EvolutionEntry[]>();
    for (const e of evolution) {
      if (!map.has(e.matchday_number)) map.set(e.matchday_number, []);
      map.get(e.matchday_number)!.push(e);
    }
    return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
  }, [evolution]);

  const participants = useMemo(() => {
    if (matchdays.length === 0) return [];
    const lastMd = matchdays[matchdays.length - 1][1];
    return [...lastMd].sort((a, b) => b.cumulative - a.cumulative);
  }, [matchdays]);

  if (matchdays.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-vpv-text-muted">
        Sin datos de evolucion
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-bg text-left text-xs text-vpv-text-muted">
              <th className="sticky left-0 bg-vpv-bg px-3 py-2">Jornada</th>
              {participants.map((p) => (
                <th key={p.participant_id} className="px-3 py-2 text-right">
                  {p.display_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matchdays.map(([mdNumber, entries]) => (
              <tr
                key={mdNumber}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
              >
                <td className="sticky left-0 bg-vpv-card px-3 py-1.5 font-medium text-vpv-text">
                  J{mdNumber}
                </td>
                {participants.map((p) => {
                  const entry = entries.find(
                    (e) => e.participant_id === p.participant_id,
                  );
                  return (
                    <td
                      key={p.participant_id}
                      className="px-3 py-1.5 text-right text-vpv-text-muted"
                    >
                      {entry ? (
                        <span title={`+${entry.points}`}>
                          {entry.cumulative}
                        </span>
                      ) : (
                        "\u2014"
                      )}
                    </td>
                  );
                })}
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
 *  - Most lined-up players table (top 15)
 *  - Matchday averages table with range column
 */
function LeagueTab({
  formations,
  mostLinedUp,
  matchdayAverages,
  records,
}: {
  formations: FormationUsage[];
  mostLinedUp: MostLinedUpPlayer[];
  matchdayAverages: MatchdayAverageEntry[];
  records: RecordEntry[];
}) {
  return (
    <div className="space-y-4">
      {/* Records */}
      {records.length > 0 && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
          <div className="border-b border-vpv-border px-4 py-3">
            <h3 className="font-semibold text-vpv-text">Records</h3>
          </div>
          <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
            {records.map((r, i) => (
              <div
                key={i}
                className="rounded-lg border border-vpv-border bg-vpv-bg p-3"
              >
                <p className="text-xs text-vpv-text-muted">{r.label}</p>
                <p className="text-lg font-bold text-vpv-accent">{r.value}</p>
                <p className="text-xs text-vpv-text-muted">{r.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Formation usage */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h3 className="font-semibold text-vpv-text">Uso de formaciones</h3>
        </div>
        <div className="p-4">
          {formations.length === 0 ? (
            <p className="text-sm text-vpv-text-muted">Sin datos</p>
          ) : (
            <div className="space-y-2">
              {formations.map((f) => {
                const maxCount = formations[0].usage_count;
                const pct = maxCount > 0 ? (f.usage_count / maxCount) * 100 : 0;
                return (
                  <div key={f.formation} className="flex items-center gap-3">
                    <span className="w-20 text-sm font-medium text-vpv-text">
                      {f.formation}
                    </span>
                    <div className="flex-1">
                      <div className="h-5 rounded-full bg-vpv-border">
                        <div
                          className="flex h-5 items-center rounded-full bg-vpv-accent px-2 text-xs font-medium text-white"
                          style={{ width: `${Math.max(pct, 8)}%` }}
                        >
                          {f.usage_count}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Most lined up */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h3 className="font-semibold text-vpv-text">
            Jugadores mas alineados
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-vpv-border bg-vpv-bg text-left text-xs text-vpv-text-muted">
                <th className="px-3 py-2">#</th>
                <th className="px-3 py-2">Jugador</th>
                <th className="px-3 py-2">Pos</th>
                <th className="px-3 py-2">Equipo</th>
                <th className="px-3 py-2 text-right">Veces</th>
              </tr>
            </thead>
            <tbody>
              {mostLinedUp.map((p, i) => (
                <tr
                  key={p.player_id}
                  className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                >
                  <td className="px-3 py-1.5 text-vpv-text-muted">{i + 1}</td>
                  <td className="px-3 py-1.5 font-medium text-vpv-text">
                    {p.display_name}
                  </td>
                  <td className="px-3 py-1.5">
                    <span
                      className={`rounded px-1.5 py-0.5 text-xs font-medium ${POS_COLOR[p.position] ?? "bg-vpv-bg text-vpv-text-muted"}`}
                    >
                      {p.position}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-vpv-text-muted">
                    {p.team_name}
                  </td>
                  <td className="px-3 py-1.5 text-right font-medium text-vpv-accent">
                    {p.times_lined_up}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Matchday averages */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h3 className="font-semibold text-vpv-text">Medias por jornada</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-vpv-border bg-vpv-bg text-left text-xs text-vpv-text-muted">
                <th className="px-3 py-2">Jornada</th>
                <th className="px-3 py-2 text-right">Media</th>
                <th className="px-3 py-2 text-right">Max</th>
                <th className="px-3 py-2 text-right">Min</th>
                <th className="px-3 py-2 text-right">Rango</th>
              </tr>
            </thead>
            <tbody>
              {matchdayAverages.map((md) => (
                <tr
                  key={md.matchday_number}
                  className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                >
                  <td className="px-3 py-1.5 font-medium text-vpv-text">
                    J{md.matchday_number}
                  </td>
                  <td className="px-3 py-1.5 text-right font-medium text-vpv-accent">
                    {md.avg_points.toFixed(1)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-green-400">
                    {md.max_points}
                  </td>
                  <td className="px-3 py-1.5 text-right text-red-400">
                    {md.min_points}
                  </td>
                  <td className="px-3 py-1.5 text-right text-vpv-text-muted">
                    {md.max_points - md.min_points}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function AdminEstadisticasPage() {
  const [seasons, setSeasons] = useState<SeasonOption[]>([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<StatTab>("jugadores");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data per tab
  const [players, setPlayers] = useState<PlayerStatRow[]>([]);
  const [breakdowns, setBreakdowns] = useState<ParticipantBreakdown[]>([]);
  const [extremes, setExtremes] = useState<ParticipantExtremes[]>([]);
  const [evolution, setEvolution] = useState<EvolutionEntry[]>([]);
  const [formations, setFormations] = useState<FormationUsage[]>([]);
  const [mostLinedUp, setMostLinedUp] = useState<MostLinedUpPlayer[]>([]);
  const [matchdayAverages, setMatchdayAverages] = useState<
    MatchdayAverageEntry[]
  >([]);
  const [records, setRecords] = useState<RecordEntry[]>([]);
  const [tabLoading, setTabLoading] = useState(false);

  const fetchSeasons = useCallback(async () => {
    try {
      const data = await apiClient.get<SeasonOption[]>("/seasons");
      setSeasons(data);
      if (data.length > 0 && selectedSeasonId === null) {
        const active = data.find((s) => s.status === "active") ?? data[0];
        setSelectedSeasonId(active.id);
      }
    } catch (err) {
      setError(
        `Error al cargar temporadas: ${err instanceof Error ? err.message : "desconocido"}`,
      );
    } finally {
      setLoading(false);
    }
  }, [selectedSeasonId]);

  useEffect(() => {
    fetchSeasons();
  }, [fetchSeasons]);

  const fetchTabData = useCallback(
    async (tab: StatTab, seasonId: number) => {
      setTabLoading(true);
      setError(null);
      try {
        if (tab === "jugadores") {
          const data = await apiClient.get<PlayerStatsResponse>(
            `/stats/${seasonId}/players`,
          );
          setPlayers(data.players);
        } else if (tab === "participantes") {
          const data = await apiClient.get<ParticipantStatsResponse>(
            `/stats/${seasonId}/participants`,
          );
          setBreakdowns(data.breakdowns);
          setExtremes(data.extremes);
          setEvolution(data.evolution);
        } else if (tab === "liga") {
          const data = await apiClient.get<LeagueStatsResponse>(
            `/stats/${seasonId}/league`,
          );
          setFormations(data.formations);
          setMostLinedUp(data.most_lined_up);
          setMatchdayAverages(data.matchday_averages);
          setRecords(data.records);
        }
      } catch (err) {
        setError(
          `Error al cargar ${tab}: ${err instanceof Error ? err.message : "desconocido"}`,
        );
      } finally {
        setTabLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (selectedSeasonId !== null) {
      fetchTabData(activeTab, selectedSeasonId);
    }
  }, [selectedSeasonId, activeTab, fetchTabData]);

  if (loading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-12 animate-pulse rounded-lg bg-vpv-border"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-vpv-text-muted">Temporada:</label>
        <select
          value={selectedSeasonId ?? ""}
          onChange={(e) => setSelectedSeasonId(Number(e.target.value))}
          className="rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text"
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && <ErrorBanner message={error} />}

      {/* Sub-tabs */}
      <div className="flex gap-1 border-b border-vpv-border pb-px">
        {STAT_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`rounded-t-md px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === key
                ? "border-b-2 border-vpv-accent text-vpv-accent"
                : "text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      {tabLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded-lg bg-vpv-border"
            />
          ))}
        </div>
      ) : (
        <>
          {activeTab === "jugadores" && <PlayersTab players={players} />}
          {activeTab === "participantes" && (
            <ParticipantsTab
              breakdowns={breakdowns}
              extremes={extremes}
              evolution={evolution}
            />
          )}
          {activeTab === "liga" && (
            <LeagueTab
              formations={formations}
              mostLinedUp={mostLinedUp}
              matchdayAverages={matchdayAverages}
              records={records}
            />
          )}
        </>
      )}
    </div>
  );
}
