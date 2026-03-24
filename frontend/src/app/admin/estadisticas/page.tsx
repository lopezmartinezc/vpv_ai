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
  AdvancedPlayerStat,
  AdvancedPlayersResponse,
  PositionAnalysis,
  PositionValueResponse,
  DraftHistoryResponse,
  PickValuePoint,
  PositionRoundValue,
  RateEntry,
  TeamDependencyEntry,
  TeamDependencyResponse,
  ComparePlayerAxis,
  ComparePlayersResponse,
  PlayerSplit,
  PlayerSplitsResponse,
  DraftValuePlayer,
  DraftValueResponse,
} from "@/types";

// ---------------------------------------------------------------------------
// Sub-tabs
// ---------------------------------------------------------------------------

const STAT_TABS = [
  { key: "jugadores", label: "Jugadores" },
  { key: "participantes", label: "Participantes" },
  { key: "liga", label: "Liga" },
  { key: "avanzado", label: "Avanzado" },
  { key: "draft", label: "Draft Valor" },
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
// Advanced Tab
// ---------------------------------------------------------------------------

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

function AdvancedTab({ players }: { players: AdvancedPlayerStat[] }) {
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
// Positions Tab (Phase 2)
// ---------------------------------------------------------------------------

const TIER_COLORS: Record<number, string> = {
  1: "border-amber-500/50 bg-amber-500/10",
  2: "border-blue-500/50 bg-blue-500/10",
  3: "border-emerald-500/50 bg-emerald-500/10",
  4: "border-zinc-500/50 bg-zinc-500/10",
};

const TIER_LABEL_COLORS: Record<number, string> = {
  1: "text-amber-400",
  2: "text-blue-400",
  3: "text-emerald-400",
  4: "text-zinc-400",
};

function PositionsTab({ positions }: { positions: PositionAnalysis[] }) {
  if (positions.length === 0) {
    return (
      <p className="py-6 text-center text-vpv-text-muted">
        Sin datos de posiciones
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {positions.map((pos) => (
          <div
            key={pos.position}
            className="rounded-lg border border-vpv-border bg-vpv-card p-3"
          >
            <div className="flex items-center justify-between">
              <span
                className={`rounded px-1.5 py-0.5 text-xs font-bold ${POS_COLOR[pos.position] ?? ""}`}
              >
                {pos.position}
              </span>
              <span className="text-xs text-vpv-text-muted">
                {pos.player_count} jugadores
              </span>
            </div>
            <div className="mt-2 space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-vpv-text-muted">Reemplazo</span>
                <span className="tabular-nums text-vpv-text">
                  {pos.replacement_level.toFixed(0)} pts
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-vpv-text-muted">Media</span>
                <span className="tabular-nums text-vpv-text">
                  {pos.avg_points.toFixed(0)} pts
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-vpv-text-muted">Escasez</span>
                <span
                  className={`tabular-nums font-medium ${
                    pos.scarcity_index < 0.05
                      ? "text-red-400"
                      : pos.scarcity_index < 0.1
                        ? "text-amber-400"
                        : "text-green-400"
                  }`}
                >
                  {(pos.scarcity_index * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tier breakdown per position */}
      <div className="grid gap-4 lg:grid-cols-2">
        {positions.map((pos) => (
          <div
            key={pos.position}
            className="rounded-lg border border-vpv-border bg-vpv-bg p-4"
          >
            <h3 className="mb-3 text-sm font-semibold text-vpv-text">
              <span
                className={`mr-2 rounded px-1.5 py-0.5 text-xs font-bold ${POS_COLOR[pos.position] ?? ""}`}
              >
                {pos.position}
              </span>
              Tiers
            </h3>
            <div className="space-y-2">
              {pos.tiers.map((tier) => (
                <div
                  key={tier.tier}
                  className={`rounded border p-2 ${TIER_COLORS[tier.tier] ?? ""}`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span
                      className={`text-xs font-semibold ${TIER_LABEL_COLORS[tier.tier] ?? ""}`}
                    >
                      T{tier.tier} — {tier.label}
                    </span>
                    <span className="text-[10px] text-vpv-text-muted">
                      {tier.min_points.toFixed(0)}–{tier.max_points.toFixed(0)}{" "}
                      pts
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {tier.players.map((p) => (
                      <span
                        key={p.player_id}
                        className="inline-flex items-center gap-1 rounded bg-vpv-bg/60 px-1.5 py-0.5 text-[11px]"
                        title={`${p.display_name} (${p.team_name}) — PAR: ${p.par > 0 ? "+" : ""}${p.par.toFixed(0)}`}
                      >
                        <span className="truncate text-vpv-text">
                          {p.display_name}
                        </span>
                        <span
                          className={`tabular-nums font-medium ${
                            p.par > 0 ? "text-green-400" : "text-red-400"
                          }`}
                        >
                          {p.par > 0 ? "+" : ""}
                          {p.par.toFixed(0)}
                        </span>
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-vpv-text-muted">
        <span>PAR = puntos sobre nivel de reemplazo</span>
        <span>Escasez = % jugadores elite vs total</span>
        <span>Nivel reemplazo = jugador N+1 (no drafteado)</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Draft Tab (Phase 3)
// ---------------------------------------------------------------------------

function DraftTab({ data }: { data: DraftHistoryResponse }) {
  const { pick_value_curve, position_by_round, bust_rate, steal_rate } = data;

  // Group position_by_round by round for heatmap
  const rounds = useMemo(() => {
    const map = new Map<number, Map<string, PositionRoundValue>>();
    for (const pr of position_by_round) {
      if (!map.has(pr.round_number)) map.set(pr.round_number, new Map());
      map.get(pr.round_number)!.set(pr.position, pr);
    }
    return map;
  }, [position_by_round]);

  const roundNumbers = useMemo(
    () => [...rounds.keys()].sort((a, b) => a - b),
    [rounds],
  );
  const positions = ["POR", "DEF", "MED", "DEL"];

  // Find max avg for color scale
  const maxAvg = useMemo(
    () => Math.max(...position_by_round.map((pr) => pr.avg_total_points), 1),
    [position_by_round],
  );

  return (
    <div className="space-y-6">
      {/* Pick Value Curve */}
      <div className="rounded-lg border border-vpv-border bg-vpv-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-vpv-text">
          Curva de Valor por Pick
        </h3>
        {pick_value_curve.length > 0 ? (
          <PickValueChart points={pick_value_curve} />
        ) : (
          <p className="text-sm text-vpv-text-muted">Sin datos de draft</p>
        )}
      </div>

      {/* Position by Round Heatmap */}
      {roundNumbers.length > 0 && (
        <div className="rounded-lg border border-vpv-border bg-vpv-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-vpv-text">
            Rendimiento por Posicion y Ronda
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-vpv-border">
                  <th className="px-2 py-1.5 text-left text-vpv-text-muted">
                    Ronda
                  </th>
                  {positions.map((pos) => (
                    <th
                      key={pos}
                      className="px-2 py-1.5 text-center text-vpv-text-muted"
                    >
                      {pos}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {roundNumbers.map((rn) => (
                  <tr
                    key={rn}
                    className="border-b border-vpv-border/50 last:border-0"
                  >
                    <td className="px-2 py-1 font-medium text-vpv-text-muted">
                      R{rn}
                    </td>
                    {positions.map((pos) => {
                      const val = rounds.get(rn)?.get(pos);
                      if (!val)
                        return (
                          <td
                            key={pos}
                            className="px-2 py-1 text-center text-vpv-text-muted"
                          >
                            —
                          </td>
                        );
                      const intensity = Math.min(
                        val.avg_total_points / maxAvg,
                        1,
                      );
                      const bg =
                        intensity > 0.7
                          ? "bg-green-500/30"
                          : intensity > 0.4
                            ? "bg-amber-500/20"
                            : "bg-red-500/15";
                      return (
                        <td
                          key={pos}
                          className={`px-2 py-1 text-center tabular-nums ${bg}`}
                          title={`${val.pick_count} picks`}
                        >
                          {val.avg_total_points.toFixed(0)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Bust & Steal Rates */}
      <div className="grid gap-3 sm:grid-cols-2">
        <RateCard
          title="Bust Rate"
          subtitle="Picks tempranos que rinden bajo la mediana"
          entries={bust_rate}
          colorClass="text-red-400"
        />
        <RateCard
          title="Steal Rate"
          subtitle="Picks tardios que superan mediana de rondas 1-3"
          entries={steal_rate}
          colorClass="text-green-400"
        />
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-vpv-text-muted">
        <span>Curva = avg puntos temporada por pick (todas las temporadas)</span>
        <span>Bust = pick rondas 1-3 bajo mediana global</span>
        <span>Steal = pick rondas 15+ sobre mediana rondas 1-3</span>
      </div>
    </div>
  );
}

/** SVG bar chart for pick value curve. */
function PickValueChart({ points }: { points: PickValuePoint[] }) {
  const maxPts = Math.max(...points.map((p) => p.avg_total_points), 1);
  const chartH = 160;
  const barW = Math.max(4, Math.min(12, 600 / points.length));
  const chartW = points.length * (barW + 2) + 20;

  return (
    <div className="overflow-x-auto">
      <svg
        width={chartW}
        height={chartH + 30}
        className="text-vpv-text"
        viewBox={`0 0 ${chartW} ${chartH + 30}`}
      >
        {points.map((p, i) => {
          const h = (p.avg_total_points / maxPts) * chartH;
          const x = i * (barW + 2) + 10;
          const y = chartH - h;
          return (
            <g key={p.pick_number}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={h}
                rx={1}
                className="fill-vpv-accent/70 hover:fill-vpv-accent"
              >
                <title>
                  Pick {p.pick_number}: {p.avg_total_points.toFixed(0)} pts
                  (n={p.sample_count})
                </title>
              </rect>
              {p.pick_number % 5 === 0 && (
                <text
                  x={x + barW / 2}
                  y={chartH + 15}
                  textAnchor="middle"
                  className="fill-current text-[9px] text-vpv-text-muted"
                >
                  {p.pick_number}
                </text>
              )}
            </g>
          );
        })}
        {/* Y-axis labels */}
        <text
          x={4}
          y={10}
          className="fill-current text-[9px] text-vpv-text-muted"
        >
          {maxPts.toFixed(0)}
        </text>
        <text
          x={4}
          y={chartH}
          className="fill-current text-[9px] text-vpv-text-muted"
        >
          0
        </text>
      </svg>
    </div>
  );
}

function RateCard({
  title,
  subtitle,
  entries,
  colorClass,
}: {
  title: string;
  subtitle: string;
  entries: RateEntry[];
  colorClass: string;
}) {
  return (
    <div className="rounded-lg border border-vpv-border bg-vpv-card p-4">
      <h4 className="text-sm font-semibold text-vpv-text">{title}</h4>
      <p className="mb-3 text-xs text-vpv-text-muted">{subtitle}</p>
      {entries.length === 0 ? (
        <p className="text-xs text-vpv-text-muted">Sin datos</p>
      ) : (
        <div className="space-y-2">
          {entries.map((e) => (
            <div key={e.round_range} className="flex items-center justify-between">
              <span className="text-xs text-vpv-text-muted">
                Rondas {e.round_range}
              </span>
              <div className="flex items-center gap-2">
                <span className={`text-sm font-semibold tabular-nums ${colorClass}`}>
                  {e.rate_pct.toFixed(1)}%
                </span>
                <span className="text-[10px] text-vpv-text-muted">
                  ({e.total_picks} picks)
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Contexto Tab (Phase 4)
// ---------------------------------------------------------------------------

function ContextoTab({
  seasonId,
  dependency,
  advancedPlayers,
}: {
  seasonId: number;
  dependency: TeamDependencyEntry[];
  advancedPlayers: AdvancedPlayerStat[];
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
        `/stats/${seasonId}/players/compare?player_ids=${compareIds.join(",")}`,
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
  }, [seasonId, compareIds]);

  // Fetch splits
  const fetchSplits = (playerId: number, name: string) => {
    setSplitPlayerId(playerId);
    setSplitPlayerName(name);
    setSplitLoading(true);
    apiClient
      .get<PlayerSplitsResponse>(
        `/stats/${seasonId}/players/${playerId}/splits`,
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

const SIGNAL_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  strong_buy: { bg: "bg-green-500/20", text: "text-green-400", label: "Comprar" },
  buy: { bg: "bg-green-500/10", text: "text-green-400", label: "Bien" },
  hold: { bg: "bg-amber-500/15", text: "text-amber-400", label: "Neutro" },
  avoid: { bg: "bg-red-500/20", text: "text-red-400", label: "Evitar" },
};

const DRAFT_SORT_OPTIONS = [
  { key: "ensemble_score", label: "Ensemble (mejor)" },
  { key: "simple_avg", label: "Media simple" },
  { key: "stability_score", label: "Seguridad" },
  { key: "productivity_score", label: "Productividad" },
  { key: "trend_score", label: "Tendencia" },
  { key: "consistency", label: "Consistencia" },
] as const;

function DraftValueTab({ seasonId }: { seasonId: number }) {
  const [data, setData] = useState<DraftValueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [posFilter, setPosFilter] = useState("");
  const [sortKey, setSortKey] = useState<string>("ensemble_score");
  const [signalFilter, setSignalFilter] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [error, setError] = useState(false);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<DraftValueResponse>(`/stats/${seasonId}/players/draft-value`)
      .then((d) => {
        if (!cancelled) { setData(d); setError(false); }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [seasonId]);

  const players = useMemo(() => {
    if (!data) return [];
    let list = data.players;
    if (posFilter) list = list.filter((p) => p.position === posFilter);
    if (signalFilter) list = list.filter((p) => p.signal === signalFilter);
    return sorted(list, sortKey as keyof DraftValuePlayer, "desc");
  }, [data, posFilter, signalFilter, sortKey]);

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded bg-vpv-border" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        Error al cargar datos de draft.{" "}
        <button onClick={() => { setLoading(true); setError(false); }} className="underline">
          Reintentar
        </button>
      </div>
    );
  }

  if (!data) return <p className="text-sm text-vpv-text-muted">Sin datos</p>;

  return (
    <div className="space-y-3">
      {/* Header info */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-3 text-xs text-vpv-text-muted">
          <span>
            <b className="text-vpv-text">{data.draft_type === "winter" ? "Draft Invierno" : "Draft Pretemporada"}</b>
            {" "}{data.season_name}
          </span>
          <span>J{data.matchdays_played} jugadas</span>
          <span>Peso historial: {(data.peso_historico * 100).toFixed(0)}%</span>
          <span>{players.length} jugadores</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex gap-0.5">
          {["", "POR", "DEF", "MED", "DEL"].map((p) => (
            <button
              key={p}
              onClick={() => setPosFilter(p)}
              className={`rounded px-2 py-1 text-[10px] font-medium ${
                posFilter === p ? "bg-vpv-accent text-white" : "border border-vpv-border text-vpv-text-muted"
              }`}
            >
              {p || "Todas"}
            </button>
          ))}
        </div>
        <div className="flex gap-0.5">
          {["", "strong_buy", "buy", "hold", "avoid"].map((s) => {
            const badge = SIGNAL_BADGE[s];
            return (
              <button
                key={s}
                onClick={() => setSignalFilter(s)}
                className={`rounded px-2 py-1 text-[10px] font-medium ${
                  signalFilter === s ? "bg-vpv-accent text-white" : "border border-vpv-border text-vpv-text-muted"
                }`}
              >
                {badge?.label || "Todos"}
              </button>
            );
          })}
        </div>
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value)}
          className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-[10px] text-vpv-text"
        >
          {DRAFT_SORT_OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden">
        {/* Desktop header */}
        <div className="hidden border-b border-vpv-border bg-vpv-bg px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted md:flex">
          <span className="w-8">#</span>
          <span className="flex-1">Jugador</span>
          <span className="w-12 text-center">Pos</span>
          <span className="w-14 text-right">Ens</span>
          <span className="w-14 text-right">Avg</span>
          <span className="w-14 text-right">Form</span>
          <span className="w-14 text-right">Stab</span>
          <span className="w-14 text-right">Trend</span>
          <span className="w-10 text-center">Cons</span>
          <span className="w-16 text-center">Signal</span>
        </div>

        <div className="divide-y divide-vpv-border/50">
          {(showAll ? players : players.slice(0, 100)).map((p, i) => {
            const badge = SIGNAL_BADGE[p.signal] ?? SIGNAL_BADGE.hold;
            const isExpanded = expandedId === p.player_id;

            return (
              <div key={p.player_id}>
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : p.player_id)}
                  className={`flex w-full items-center px-3 py-1.5 text-left hover:bg-vpv-bg/30 ${isExpanded ? "bg-vpv-bg/40" : ""}`}
                >
                  {/* Mobile: compact */}
                  <div className="flex flex-1 items-center gap-2 md:hidden">
                    <span className="w-6 text-[10px] text-vpv-text-muted">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-vpv-text">{p.display_name}</p>
                      <p className="text-[10px] text-vpv-text-muted">{p.team_name} · {p.position}</p>
                    </div>
                    <span className="text-xs font-bold tabular-nums text-vpv-text">{p.ensemble_score.toFixed(1)}</span>
                    <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${badge.bg} ${badge.text}`}>
                      {badge.label}
                    </span>
                  </div>

                  {/* Desktop: full row */}
                  <div className="hidden w-full items-center md:flex">
                    <span className="w-8 text-[10px] text-vpv-text-muted">{i + 1}</span>
                    <span className="flex-1 truncate text-xs font-medium text-vpv-text">
                      {p.display_name}
                      <span className="ml-1 text-[10px] font-normal text-vpv-text-muted">{p.team_name}</span>
                      {p.seasons_played === 1 && (
                        <span className="ml-1 rounded bg-amber-500/15 px-1 text-[8px] text-amber-400">NEW</span>
                      )}
                    </span>
                    <span className="w-12 text-center text-[10px] text-vpv-text-muted">{p.position}</span>
                    <span className="w-14 text-right text-xs font-bold tabular-nums text-vpv-accent">{p.ensemble_score.toFixed(1)}</span>
                    <span className="w-14 text-right text-xs tabular-nums text-vpv-text-muted">{p.simple_avg.toFixed(1)}</span>
                    <span className="w-14 text-right text-xs tabular-nums text-vpv-text-muted">
                      {p.second_half_score?.toFixed(1) ?? "—"}
                    </span>
                    <span className="w-14 text-right text-xs tabular-nums text-vpv-text-muted">{p.stability_score.toFixed(1)}</span>
                    <span className={`w-14 text-right text-xs tabular-nums ${
                      p.career_trend_pct && p.career_trend_pct > 0.05 ? "text-green-400" :
                      p.career_trend_pct && p.career_trend_pct < -0.05 ? "text-red-400" : "text-vpv-text-muted"
                    }`}>
                      {p.career_trend_pct != null ? `${p.career_trend_pct > 0 ? "+" : ""}${(p.career_trend_pct * 100).toFixed(0)}%` : "—"}
                    </span>
                    <span className="w-10 text-center">
                      <span className={`inline-block h-2 w-2 rounded-full ${
                        p.consistency > 0.6 ? "bg-green-500" : p.consistency > 0.3 ? "bg-amber-500" : "bg-red-500"
                      }`} />
                    </span>
                    <span className={`w-16 text-center rounded px-1.5 py-0.5 text-[9px] font-bold ${badge.bg} ${badge.text}`}>
                      {badge.label}
                    </span>
                  </div>
                </button>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="border-t border-vpv-border/30 bg-vpv-bg/20 px-4 py-2.5 text-xs">
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3 md:grid-cols-4">
                      <div>
                        <span className="text-vpv-text-muted">Temporadas: </span>
                        <span className="font-medium text-vpv-text">{p.seasons_played}</span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Partidos: </span>
                        <span className="font-medium text-vpv-text">{p.games_played}</span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Pts totales: </span>
                        <span className="font-medium text-vpv-text">{p.total_points.toFixed(0)}</span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Disponibilidad: </span>
                        <span className={`font-medium ${p.availability > 0.8 ? "text-green-400" : p.availability > 0.6 ? "text-amber-400" : "text-red-400"}`}>
                          {(p.availability * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Goles: </span>
                        <span className="font-medium text-vpv-text">{p.goals}</span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Asistencias: </span>
                        <span className="font-medium text-vpv-text">{p.assists}</span>
                      </div>
                      {p.marca_avg != null && (
                        <div>
                          <span className="text-vpv-text-muted">Marca: </span>
                          <span className="font-medium text-vpv-text">{p.marca_avg.toFixed(1)} estrellas</span>
                        </div>
                      )}
                      {p.as_avg != null && (
                        <div>
                          <span className="text-vpv-text-muted">AS: </span>
                          <span className="font-medium text-vpv-text">{p.as_avg.toFixed(1)} picas</span>
                        </div>
                      )}
                      {p.second_half_avg != null && (
                        <div>
                          <span className="text-vpv-text-muted">2a mitad: </span>
                          <span className="font-medium text-vpv-text">{p.second_half_avg.toFixed(1)} pts/j</span>
                        </div>
                      )}
                      <div>
                        <span className="text-vpv-text-muted">Productividad: </span>
                        <span className="font-medium text-vpv-text">{p.productivity_score.toFixed(1)}</span>
                      </div>
                    </div>
                    {p.signal_reasons.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {p.signal_reasons.map((r, ri) => (
                          <span
                            key={ri}
                            className={`rounded px-1.5 py-0.5 text-[9px] ${
                              r.startsWith("En declive") || r.startsWith("Poca") || r.startsWith("Muy") || r.startsWith("Sin")
                                ? "bg-red-500/10 text-red-400"
                                : "bg-green-500/10 text-green-400"
                            }`}
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {!showAll && players.length > 100 && (
        <button
          onClick={() => setShowAll(true)}
          className="w-full rounded-lg border border-vpv-border py-2 text-xs text-vpv-text-muted hover:text-vpv-text"
        >
          Mostrando 100 de {players.length} — Ver todos
        </button>
      )}

      {/* Model legend */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">Modelos (backtested)</p>
        <div className="grid grid-cols-1 gap-1 text-[10px] sm:grid-cols-2">
          {data.model_info && Object.entries(data.model_info).map(([key, desc]) => (
            <div key={key}>
              <span className="font-medium text-vpv-text">{key}: </span>
              <span className="text-vpv-text-muted">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


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
  const [advancedPlayers, setAdvancedPlayers] = useState<AdvancedPlayerStat[]>(
    [],
  );
  const [positionData, setPositionData] = useState<PositionAnalysis[]>([]);
  const [draftData, setDraftData] = useState<DraftHistoryResponse | null>(null);
  const [dependencyData, setDependencyData] = useState<TeamDependencyEntry[]>([]);
  const [advSubTab, setAdvSubTab] = useState<"valoracion" | "posiciones" | "draft" | "contexto">("valoracion");
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
        } else if (tab === "avanzado") {
          // Fetch all advanced sub-tab data in parallel
          const [advData, posData, draftRes, depData] = await Promise.all([
            apiClient.get<AdvancedPlayersResponse>(
              `/stats/${seasonId}/players/advanced`,
            ),
            apiClient.get<PositionValueResponse>(
              `/stats/${seasonId}/positions/value`,
            ),
            apiClient.get<DraftHistoryResponse>(`/stats/draft-history`),
            apiClient.get<TeamDependencyResponse>(
              `/stats/${seasonId}/teams/dependency`,
            ),
          ]);
          setAdvancedPlayers(advData.players);
          setPositionData(posData.positions);
          setDraftData(draftRes);
          setDependencyData(depData.entries);
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
          {activeTab === "draft" && selectedSeasonId && (
            <DraftValueTab seasonId={selectedSeasonId} />
          )}
          {activeTab === "avanzado" && (
            <div className="space-y-4">
              {/* Advanced sub-tabs */}
              <div className="flex gap-1">
                {([
                  { key: "valoracion", label: "Valoracion" },
                  { key: "posiciones", label: "Posiciones" },
                  { key: "draft", label: "Historial Draft" },
                  { key: "contexto", label: "Contexto" },
                ] as const).map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => setAdvSubTab(key)}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                      advSubTab === key
                        ? "bg-vpv-accent text-white"
                        : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {advSubTab === "valoracion" && (
                <AdvancedTab players={advancedPlayers} />
              )}
              {advSubTab === "posiciones" && (
                <PositionsTab positions={positionData} />
              )}
              {advSubTab === "draft" && draftData && (
                <DraftTab data={draftData} />
              )}
              {advSubTab === "contexto" && selectedSeasonId && (
                <ContextoTab
                  seasonId={selectedSeasonId}
                  dependency={dependencyData}
                  advancedPlayers={advancedPlayers}
                />
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
