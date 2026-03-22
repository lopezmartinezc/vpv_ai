"use client";

import { useCallback, useEffect, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { apiClient } from "@/lib/api-client";

interface LogEntry {
  id: number;
  matchday_number: number | null;
  match_id: number | null;
  player_id: number | null;
  job_type: string;
  status: string;
  message: string | null;
  detail: Record<string, unknown> | null;
  created_at: string | null;
  player_name: string | null;
  match_label: string | null;
}

interface LogsResponse {
  items: LogEntry[];
  total: number;
  limit: number;
  offset: number;
}

const STATUS_OPTIONS = ["", "ok", "skip", "error"] as const;
const STATUS_LABELS: Record<string, string> = {
  "": "Todos",
  ok: "OK",
  skip: "Skip",
  error: "Error",
};
const STATUS_COLORS: Record<string, string> = {
  ok: "bg-green-500/20 text-green-400",
  skip: "bg-amber-500/20 text-amber-400",
  error: "bg-red-500/20 text-red-400",
};

const PAGE_SIZE = 50;

export default function ScrapingLogsPage() {
  const { selectedSeason } = useSeason();

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);

  // Filters
  const [matchday, setMatchday] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  // Expanded row
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const fetchLogs = useCallback(async () => {
    if (!selectedSeason) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        season_id: String(selectedSeason.id),
        limit: String(PAGE_SIZE),
        offset: String(page * PAGE_SIZE),
      });
      if (matchday) params.set("matchday", matchday);
      if (statusFilter) params.set("status", statusFilter);
      if (search) params.set("search", search);

      const data = await apiClient.get<LogsResponse>(
        `/scraping/logs?${params.toString()}`
      );
      setLogs(data.items);
      setTotal(data.total);
    } catch {
      setLogs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [selectedSeason, page, matchday, statusFilter, search]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  function handleFilter() {
    setPage(0);
    fetchLogs();
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  function formatTime(iso: string | null) {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("es-ES", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-vpv-text">Scraping Logs</h2>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-vpv-card-border bg-vpv-card p-3">
        <div>
          <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
            Jornada
          </label>
          <input
            type="number"
            value={matchday}
            onChange={(e) => setMatchday(e.target.value)}
            placeholder="Todas"
            className="w-20 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
          />
        </div>
        <div>
          <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
            Status
          </label>
          <div className="flex gap-1">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => {
                  setStatusFilter(s);
                  setPage(0);
                }}
                className={`rounded px-2.5 py-1.5 text-xs font-medium transition-colors ${
                  statusFilter === s
                    ? "bg-vpv-accent text-white"
                    : "border border-vpv-border text-vpv-text-muted hover:text-vpv-text"
                }`}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1">
          <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
            Buscar
          </label>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleFilter()}
            placeholder="Nombre jugador, error..."
            className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
          />
        </div>
        <button
          onClick={handleFilter}
          className="rounded bg-vpv-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-vpv-accent-hover"
        >
          Buscar
        </button>
      </div>

      {/* Results count */}
      <p className="text-xs text-vpv-text-muted">
        {total} resultados{totalPages > 1 && ` \u2014 pagina ${page + 1}/${totalPages}`}
      </p>

      {/* Table */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden">
        {loading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-8 animate-pulse rounded bg-vpv-border" />
            ))}
          </div>
        ) : logs.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-vpv-text-muted">
            Sin logs para estos filtros
          </p>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
                    <th className="px-3 py-2">Hora</th>
                    <th className="px-3 py-2">J</th>
                    <th className="px-3 py-2">Partido</th>
                    <th className="px-3 py-2">Jugador</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Mensaje</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <>
                      <tr
                        key={log.id}
                        onClick={() =>
                          setExpandedId(expandedId === log.id ? null : log.id)
                        }
                        className={`border-b border-vpv-border last:border-0 cursor-pointer transition-colors hover:bg-vpv-bg/50 ${
                          expandedId === log.id ? "bg-vpv-bg/50" : ""
                        }`}
                      >
                        <td className="px-3 py-2 text-xs text-vpv-text-muted whitespace-nowrap">
                          {formatTime(log.created_at)}
                        </td>
                        <td className="px-3 py-2 text-vpv-text">
                          {log.matchday_number ?? "-"}
                        </td>
                        <td className="px-3 py-2 text-vpv-text text-xs">
                          {log.match_label ?? "-"}
                        </td>
                        <td className="px-3 py-2 text-vpv-text">
                          {log.player_name ?? "-"}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[log.status] ?? "text-vpv-text-muted"}`}
                          >
                            {log.status}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs text-vpv-text-muted max-w-xs truncate">
                          {log.message}
                        </td>
                      </tr>
                      {expandedId === log.id && log.detail && (
                        <tr key={`${log.id}-detail`}>
                          <td colSpan={6} className="bg-vpv-bg/30 px-4 py-3">
                            <pre className="text-xs text-vpv-text-muted whitespace-pre-wrap font-mono">
                              {JSON.stringify(log.detail, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="divide-y divide-vpv-border md:hidden">
              {logs.map((log) => (
                <div
                  key={log.id}
                  onClick={() =>
                    setExpandedId(expandedId === log.id ? null : log.id)
                  }
                  className="cursor-pointer px-3 py-2.5 active:bg-vpv-bg/50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-vpv-text">
                        {log.player_name ?? log.match_label ?? log.message}
                      </p>
                      <p className="text-[10px] text-vpv-text-muted">
                        J{log.matchday_number} &middot;{" "}
                        {log.match_label ?? "-"} &middot;{" "}
                        {formatTime(log.created_at)}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[log.status] ?? "text-vpv-text-muted"}`}
                    >
                      {log.status}
                    </span>
                  </div>
                  {expandedId === log.id && log.detail && (
                    <pre className="mt-2 rounded bg-vpv-bg p-2 text-[10px] text-vpv-text-muted whitespace-pre-wrap font-mono">
                      {JSON.stringify(log.detail, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
            className="rounded border border-vpv-border px-3 py-1 text-xs text-vpv-text-muted disabled:opacity-30"
          >
            Anterior
          </button>
          <span className="text-xs text-vpv-text-muted">
            {page + 1} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages - 1}
            onClick={() => setPage(page + 1)}
            className="rounded border border-vpv-border px-3 py-1 text-xs text-vpv-text-muted disabled:opacity-30"
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  );
}
