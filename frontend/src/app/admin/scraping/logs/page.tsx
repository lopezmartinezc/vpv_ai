"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

const STATUS_BADGE: Record<string, string> = {
  ok: "bg-green-500/20 text-green-400",
  skip: "bg-amber-500/20 text-amber-400",
  error: "bg-red-500/20 text-red-400",
};

const PAGE_SIZE = 100;

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

export default function ScrapingLogsPage() {
  const { selectedSeason } = useSeason();

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Filters
  const [matchday, setMatchday] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  // Expanded rows
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const fetchLogs = useCallback(async () => {
    if (!selectedSeason) return;
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
      // keep previous data
    } finally {
      setLoading(false);
    }
  }, [selectedSeason, page, matchday, statusFilter, search]);

  // Initial fetch + on filter change
  useEffect(() => {
    setLoading(true);
    fetchLogs();
  }, [fetchLogs]);

  // Auto-refresh every 5s
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchLogs, 5000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, fetchLogs]);

  function applyFilter() {
    setPage(0);
  }

  function toggleExpand(id: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Compute summary stats from current page
  const summary = { ok: 0, skip: 0, error: 0 };
  for (const l of logs) {
    if (l.status in summary) summary[l.status as keyof typeof summary]++;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-vpv-text">Scraping Logs</h2>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-vpv-text-muted">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="h-3.5 w-3.5 rounded accent-vpv-accent"
            />
            Auto-refresh
          </label>
          <button
            onClick={fetchLogs}
            className="rounded border border-vpv-border px-2 py-1 text-xs text-vpv-text-muted hover:text-vpv-text"
          >
            Refrescar
          </button>
        </div>
      </div>

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
            onKeyDown={(e) => e.key === "Enter" && applyFilter()}
            placeholder="Todas"
            className="w-20 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
          />
        </div>
        <div>
          <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
            Status
          </label>
          <div className="flex gap-1">
            {(["", "ok", "skip", "error"] as const).map((s) => (
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
                {s || "Todos"}
              </button>
            ))}
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
            Buscar
          </label>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applyFilter()}
            placeholder="Jugador, equipo, error..."
            className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
          />
        </div>
        <button
          onClick={applyFilter}
          className="rounded bg-vpv-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-vpv-accent-hover"
        >
          Buscar
        </button>
      </div>

      {/* Summary bar */}
      <div className="flex items-center gap-4 text-xs text-vpv-text-muted">
        <span>{total} registros</span>
        {total > 0 && (
          <>
            <span className="text-green-400">{summary.ok} ok</span>
            <span className="text-amber-400">{summary.skip} skip</span>
            <span className="text-red-400">{summary.error} error</span>
          </>
        )}
        {totalPages > 1 && (
          <span>
            Pag {page + 1}/{totalPages}
          </span>
        )}
        {autoRefresh && (
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-400" />
            Live
          </span>
        )}
      </div>

      {/* Log entries */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden">
        {loading && logs.length === 0 ? (
          <div className="space-y-1.5 p-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <div
                key={i}
                className="h-7 animate-pulse rounded bg-vpv-border"
              />
            ))}
          </div>
        ) : logs.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-vpv-text-muted">
            Sin logs para estos filtros
          </p>
        ) : (
          <div className="divide-y divide-vpv-border">
            {logs.map((log) => {
              const isError = log.status === "error";
              const isExpanded = expandedIds.has(log.id);

              return (
                <div
                  key={log.id}
                  className={`${isExpanded ? "bg-vpv-bg/40" : ""} ${isError ? "border-l-2 border-l-red-500" : ""}`}
                >
                  <button
                    type="button"
                    onClick={() => toggleExpand(log.id)}
                    className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-vpv-bg/30"
                  >
                    {/* Status badge */}
                    <span
                      className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${STATUS_BADGE[log.status] ?? "text-vpv-text-muted"}`}
                    >
                      {log.status}
                    </span>

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-sm ${isError ? "font-medium text-red-400" : "text-vpv-text"} ${isError ? "" : "truncate"}`}
                      >
                        {log.message}
                      </p>
                      <p className="mt-0.5 text-[10px] text-vpv-text-muted">
                        {log.player_name && (
                          <span className="font-medium text-vpv-text-muted/80">
                            {log.player_name}
                          </span>
                        )}
                        {log.match_label && (
                          <span>
                            {log.player_name ? " \u00b7 " : ""}
                            {log.match_label}
                          </span>
                        )}
                        {log.matchday_number && (
                          <span> \u00b7 J{log.matchday_number}</span>
                        )}
                        <span> \u00b7 {formatTime(log.created_at)}</span>
                      </p>
                    </div>

                    {/* Expand indicator */}
                    {log.detail && (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className={`mt-1 h-4 w-4 shrink-0 text-vpv-text-muted transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      >
                        <path
                          fillRule="evenodd"
                          d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                          clipRule="evenodd"
                        />
                      </svg>
                    )}
                  </button>

                  {/* Expanded detail */}
                  {isExpanded && log.detail && (
                    <div className="border-t border-vpv-border/50 bg-vpv-bg/20 px-3 py-2">
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3 md:grid-cols-4">
                        {Object.entries(log.detail).map(([k, v]) => (
                          <div key={k}>
                            <span className="text-vpv-text-muted">{k}: </span>
                            <span className="font-medium text-vpv-text">
                              {String(v ?? "-")}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
            className="rounded border border-vpv-border px-3 py-1.5 text-xs text-vpv-text-muted disabled:opacity-30"
          >
            Anterior
          </button>
          <span className="text-xs text-vpv-text-muted">
            {page + 1} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages - 1}
            onClick={() => setPage(page + 1)}
            className="rounded border border-vpv-border px-3 py-1.5 text-xs text-vpv-text-muted disabled:opacity-30"
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  );
}
