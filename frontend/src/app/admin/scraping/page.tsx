"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LogEntry {
  ts: string;
  level: string;
  msg: string;
}

interface JobStatus {
  id: string;
  name: string;
  icon: string;
  type: "interval" | "cron" | "manual";
  interval_seconds?: number;
  schedule?: string;
  last_run_at: string | null;
  next_run_at: string | null;
  lock_held?: boolean;
  triggerable?: boolean;
  active?: boolean;
  tracked_matches?: number;
  total_events_sent?: number;
  logs?: LogEntry[];
}

interface SchedulerStatus {
  running: boolean;
  jobs: JobStatus[];
  manual_logs: LogEntry[];
}

interface SeasonSummary {
  id: number;
  name: string;
  status: string;
  matchday_current: number;
}

interface MatchEntry {
  id: number;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  counts: boolean;
  stats_ok: boolean;
  played_at: string | null;
}

interface MatchdayDetail {
  season_id: number;
  number: number;
  status: string;
  counts: boolean;
  stats_ok: boolean;
  matches: MatchEntry[];
}

interface DbLogEntry {
  id: number;
  matchday_number: number | null;
  match_id: number | null;
  status: string;
  message: string | null;
  detail: Record<string, unknown> | null;
  player_name: string | null;
  match_label: string | null;
  created_at: string | null;
}

interface DbLogsResponse {
  items: DbLogEntry[];
  total: number;
}

interface MatchLogSummary {
  matchday_number: number | null;
  match_id: number | null;
  match_label: string | null;
  ok: number;
  skip: number;
  error: number;
  total: number;
  last_at: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelative(iso: string | null): string {
  if (!iso) return "";
  const diffMs = new Date(iso).getTime() - Date.now();
  const abs = Math.abs(diffMs);
  const past = diffMs < 0;
  if (abs < 60_000) return past ? "hace <1 min" : "en <1 min";
  const mins = Math.floor(abs / 60_000);
  if (mins < 60) return past ? `hace ${mins} min` : `en ${mins} min`;
  const hours = Math.floor(mins / 60);
  return past ? `hace ${hours}h` : `en ${hours}h`;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
  });
  const time = d.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return `${date} ${time}`;
}

function formatMatchDate(iso: string | null): string {
  if (!iso) return "Sin fecha";
  const d = new Date(iso);
  const diffH = Math.round((d.getTime() - Date.now()) / 3_600_000);
  const s = d.toLocaleString("es-ES", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  if (diffH < -2) return `${s} (jugado)`;
  if (diffH < 0) return `${s} (en juego)`;
  if (diffH < 24) return `${s} (en ${diffH}h)`;
  return s;
}

const LOG_COLORS: Record<string, string> = {
  info: "text-vpv-text-muted",
  warning: "text-yellow-400",
  error: "text-red-400",
};

const STATUS_BADGE: Record<string, string> = {
  ok: "bg-green-500/20 text-green-400",
  skip: "bg-amber-500/20 text-amber-400",
  error: "bg-red-500/20 text-red-400",
};

const JOB_TRIGGER_MAP: Record<string, string> = {
  scraping_tick: "/scraping/admin/trigger",
  calendar_sync: "/scraping/admin/trigger/calendar-sync",
  deadline_check: "/scraping/admin/trigger/deadline-check",
  nightly_rescrape: "/scraping/admin/trigger/nightly-rescrape",
  live_monitor: "/scraping/admin/trigger/live-monitor",
};

const JOB_COLORS: Record<string, string> = {
  scraping_tick: "bg-vpv-accent/15 text-vpv-accent",
  calendar_sync: "bg-blue-500/15 text-blue-400",
  deadline_check: "bg-amber-500/15 text-amber-400",
  deadline_reminder: "bg-amber-500/15 text-amber-400",
  nightly_rescrape: "bg-purple-500/15 text-purple-400",
  live_monitor: "bg-green-500/15 text-green-400",
};

// ---------------------------------------------------------------------------
// JobCard component
// ---------------------------------------------------------------------------

function JobCard({
  job,
  schedulerRunning,
  onTrigger,
  onToggle,
  triggeringJob,
}: {
  job: JobStatus;
  schedulerRunning: boolean;
  onTrigger: (jobId: string) => void;
  onToggle?: () => void;
  triggeringJob: string | null;
}) {
  const [showLogs, setShowLogs] = useState(false);
  const logs = job.logs ?? [];
  const lastLogs = logs.slice(-30);
  const isLive = job.id === "live_monitor";

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-center justify-between border-b border-vpv-border px-3 py-2">
        <div className="flex items-center gap-2">
          <span
            className={`flex h-7 w-7 items-center justify-center rounded-md text-xs font-bold ${JOB_COLORS[job.id] ?? "bg-vpv-border text-vpv-text-muted"}`}
          >
            {job.icon}
          </span>
          <div>
            <h3 className="text-sm font-semibold text-vpv-text">{job.name}</h3>
            <p className="text-[10px] text-vpv-text-muted">
              {job.type === "cron" && job.schedule
                ? job.schedule
                : job.interval_seconds
                  ? job.interval_seconds >= 60
                    ? `Cada ${Math.floor(job.interval_seconds / 60)} min`
                    : `Cada ${job.interval_seconds}s`
                  : "Manual"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {job.lock_held && (
            <span className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-[10px] font-medium text-yellow-400">
              En curso
            </span>
          )}
          {isLive && onToggle && (
            <button
              onClick={onToggle}
              className={`rounded px-2 py-0.5 text-[10px] font-bold transition-colors ${
                job.active
                  ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                  : "bg-vpv-border text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {job.active ? "ON" : "OFF"}
            </button>
          )}
          {job.triggerable && (
            <button
              onClick={() => onTrigger(job.id)}
              disabled={!schedulerRunning || triggeringJob !== null}
              className="rounded bg-vpv-accent/10 px-2 py-0.5 text-[10px] font-medium text-vpv-accent hover:bg-vpv-accent/20 disabled:opacity-40"
            >
              {triggeringJob === job.id ? "..." : "Forzar"}
            </button>
          )}
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-x-3 px-3 py-2 text-[11px]">
        <div>
          <span className="text-vpv-text-muted">Ultimo </span>
          <span className="font-medium text-vpv-text">
            {formatRelative(job.last_run_at) || "\u2014"}
          </span>
        </div>
        <div>
          <span className="text-vpv-text-muted">Proximo </span>
          <span className="font-medium text-vpv-text">
            {formatRelative(job.next_run_at) || "\u2014"}
          </span>
        </div>
        {isLive && (
          <>
            <div>
              <span className="text-vpv-text-muted">En curso </span>
              <span className="font-medium text-green-400">
                {job.tracked_matches ?? 0} partidos
              </span>
            </div>
            <div>
              <span className="text-vpv-text-muted">Enviados </span>
              <span className="font-medium text-vpv-text">
                {job.total_events_sent ?? 0} eventos
              </span>
            </div>
          </>
        )}
      </div>

      {/* Logs toggle */}
      {logs.length > 0 && (
        <div className="border-t border-vpv-border">
          <button
            type="button"
            onClick={() => setShowLogs((p) => !p)}
            className="flex w-full items-center justify-between px-3 py-1 text-[10px] text-vpv-text-muted hover:text-vpv-text"
          >
            <span>Logs ({logs.length})</span>
            <span>{showLogs ? "\u25B2" : "\u25BC"}</span>
          </button>
          {showLogs && (
            <div className="max-h-40 overflow-y-auto border-t border-vpv-border/50 bg-vpv-bg/50 px-2 py-1 font-mono text-[10px] leading-relaxed">
              {lastLogs.map((e, i) => (
                <div key={i} className="flex gap-1.5">
                  <span className="shrink-0 text-vpv-text-muted/50">
                    {formatTime(e.ts)}
                  </span>
                  <span className={LOG_COLORS[e.level] ?? "text-vpv-text-muted"}>
                    {e.msg}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminScrapingPage() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggeringJob, setTriggeringJob] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [scrapeResult, setScrapeResult] = useState<string | null>(null);

  // Season + matchday
  const [seasons, setSeasons] = useState<SeasonSummary[]>([]);
  const [manualSeason, setManualSeason] = useState("");
  const [manualMatchday, setManualMatchday] = useState("");
  const [matchdayDetail, setMatchdayDetail] = useState<MatchdayDetail | null>(null);
  const [scrapingMatchId, setScrapingMatchId] = useState<number | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // Inline match logs
  const [matchLogs, setMatchLogs] = useState<Record<number, DbLogEntry[]>>({});
  const [expandedLogs, setExpandedLogs] = useState<Set<number>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // DB logs section — grouped by match
  const [logSummary, setLogSummary] = useState<MatchLogSummary[]>([]);
  const [logJobType, setLogJobType] = useState("");
  const [logMatchday, setLogMatchday] = useState("");
  const [showDbLogs, setShowDbLogs] = useState(false);
  const [expandedLogMatch, setExpandedLogMatch] = useState<number | null>(null);
  const [expandedLogEntries, setExpandedLogEntries] = useState<DbLogEntry[]>([]);

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiClient.get<SchedulerStatus>("/scraping/admin/status");
      setStatus(data);
    } catch {
      /* */
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMatchday = useCallback(async (sid: number, num: number) => {
    try {
      setMatchdayDetail(
        await apiClient.get<MatchdayDetail>(`/matchdays/${sid}/${num}`)
      );
    } catch {
      setMatchdayDetail(null);
    }
  }, []);

  const fetchMatchLogs = useCallback(
    async (matchId: number) => {
      if (!manualSeason) return;
      try {
        const data = await apiClient.get<DbLogsResponse>(
          `/scraping/logs?season_id=${manualSeason}&match_id=${matchId}&limit=200`
        );
        setMatchLogs((prev) => ({ ...prev, [matchId]: data.items }));
      } catch {
        /* */
      }
    },
    [manualSeason]
  );

  const fetchLogSummary = useCallback(async () => {
    if (!manualSeason) return;
    const params = new URLSearchParams({ season_id: manualSeason });
    if (logMatchday) params.set("matchday", logMatchday);
    if (logJobType) params.set("job_type", logJobType);
    try {
      const data = await apiClient.get<MatchLogSummary[]>(
        `/scraping/logs/summary?${params.toString()}`
      );
      setLogSummary(data);
    } catch {
      /* */
    }
  }, [manualSeason, logMatchday, logJobType]);

  async function fetchMatchLogEntries(matchId: number) {
    if (!manualSeason) return;
    try {
      const data = await apiClient.get<DbLogsResponse>(
        `/scraping/logs?season_id=${manualSeason}&match_id=${matchId}&limit=200`
      );
      setExpandedLogEntries(data.items);
    } catch {
      /* */
    }
  }

  // ---------------------------------------------------------------------------
  // Effects
  // ---------------------------------------------------------------------------

  useEffect(() => {
    fetchStatus();
    apiClient.get<SeasonSummary[]>("/seasons").then((all) => {
      setSeasons(all);
      const active = all.find((s) => s.status === "active") ?? all[0];
      if (active) {
        setManualSeason(String(active.id));
        setManualMatchday(String(active.matchday_current));
        fetchMatchday(active.id, active.matchday_current);
      }
    });
    const interval = setInterval(fetchStatus, 10_000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchMatchday]);

  useEffect(() => {
    if (showDbLogs) fetchLogSummary();
  }, [showDbLogs, fetchLogSummary]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function startLogPolling(matchId: number) {
    if (pollRef.current) clearInterval(pollRef.current);
    setExpandedLogs((prev) => new Set(prev).add(matchId));
    pollRef.current = setInterval(() => fetchMatchLogs(matchId), 2000);
  }

  function stopLogPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function handleAction(action: "start" | "stop") {
    setActionLoading(action);
    try {
      setStatus(
        await apiClient.post<SchedulerStatus>(`/scraping/admin/${action}`, {})
      );
    } catch {
      /* */
    } finally {
      setActionLoading(null);
    }
  }

  async function handleTriggerJob(jobId: string) {
    const ep = JOB_TRIGGER_MAP[jobId];
    if (!ep) return;
    setTriggeringJob(jobId);
    try {
      await apiClient.post(ep, {});
      setTimeout(fetchStatus, 1500);
    } catch {
      /* */
    } finally {
      setTriggeringJob(null);
    }
  }

  async function handleToggleLiveMonitor() {
    try {
      await apiClient.post("/scraping/admin/live-monitor/toggle", {});
      fetchStatus();
    } catch {
      /* */
    }
  }

  async function handleScrapeMatch(matchId: number) {
    if (!manualSeason || !manualMatchday) return;
    const ctrl = new AbortController();
    setAbortController(ctrl);
    setScrapingMatchId(matchId);
    setMatchLogs((prev) => ({ ...prev, [matchId]: [] }));
    startLogPolling(matchId);
    try {
      const data = await apiClient.post<{
        processed?: number;
        errors?: number;
        error_details?: string[];
      }>(`/scraping/match/${manualSeason}/${manualMatchday}/${matchId}`, {}, {
        signal: ctrl.signal,
      });
      setScrapeResult(
        `Procesados: ${data.processed ?? 0}, Errores: ${data.errors ?? 0}`
      );
      fetchMatchday(Number(manualSeason), Number(manualMatchday));
    } catch {
      /* */
    } finally {
      stopLogPolling();
      await fetchMatchLogs(matchId);
      setScrapingMatchId(null);
      setAbortController(null);
    }
  }

  async function handleScrapeMatchday() {
    setActionLoading("scrape");
    setScrapeResult(null);
    try {
      const data = await apiClient.post<{
        processed?: number;
        skipped?: number;
        errors?: number;
        error_details?: string[];
      }>(`/scraping/matchday/${manualSeason}/${manualMatchday}`, {});
      const details = data.error_details ?? [];
      let msg = `Procesados: ${data.processed ?? 0}, Saltados: ${data.skipped ?? 0}, Errores: ${data.errors ?? 0}`;
      if (details.length > 0) msg += "\n" + details.join("\n");
      setScrapeResult(msg);
      fetchMatchday(Number(manualSeason), Number(manualMatchday));
      fetchStatus();
    } catch {
      setScrapeResult("Error al ejecutar scraping");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleCalendar() {
    setActionLoading("calendar");
    try {
      const d = await apiClient.post<Record<string, number>>(
        `/scraping/calendar/${manualSeason}`,
        {}
      );
      setScrapeResult(
        `Resultados: ${d.scores_updated ?? 0}, Fechas: ${d.dates_updated ?? 0}`
      );
      fetchMatchday(Number(manualSeason), Number(manualMatchday));
    } catch {
      setScrapeResult("Error calendario");
    } finally {
      setActionLoading(null);
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="space-y-3 py-4">
        <div className="h-12 animate-pulse rounded-lg bg-vpv-border" />
        <div className="grid gap-3 md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-lg bg-vpv-border" />
          ))}
        </div>
      </div>
    );
  }

  const jobs = status?.jobs ?? [];
  const playedCount =
    matchdayDetail?.matches.filter((m) => m.home_score !== null).length ?? 0;

  return (
    <div className="space-y-4">
      {/* ── Scheduler control ── */}
      <div className="flex items-center justify-between rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              status?.running
                ? "bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]"
                : "bg-red-500"
            }`}
          />
          <span className="text-sm font-semibold text-vpv-text">
            {status?.running ? "Scheduler activo" : "Scheduler detenido"}
          </span>
        </div>
        <button
          onClick={() => handleAction(status?.running ? "stop" : "start")}
          disabled={actionLoading !== null}
          className={`rounded px-3 py-1 text-xs font-medium text-white disabled:opacity-50 ${
            status?.running
              ? "bg-red-600 hover:bg-red-700"
              : "bg-green-600 hover:bg-green-700"
          }`}
        >
          {status?.running ? "Detener" : "Iniciar"}
        </button>
      </div>

      {/* ── Jobs grid ── */}
      <div className="grid gap-3 md:grid-cols-2">
        {jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            schedulerRunning={status?.running ?? false}
            onTrigger={handleTriggerJob}
            onToggle={job.id === "live_monitor" ? handleToggleLiveMonitor : undefined}
            triggeringJob={triggeringJob}
          />
        ))}
      </div>

      {/* ── Manual scraping ── */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-2.5">
          <h2 className="text-sm font-semibold text-vpv-text">Scraping manual</h2>
        </div>
        <div className="space-y-3 px-4 py-3">
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <label className="mb-0.5 block text-[10px] text-vpv-text-muted">
                Temporada
              </label>
              <select
                value={manualSeason}
                onChange={(e) => {
                  setManualSeason(e.target.value);
                  const s = seasons.find((s) => String(s.id) === e.target.value);
                  if (s) setManualMatchday(String(s.matchday_current));
                }}
                className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-sm text-vpv-text"
              >
                {seasons.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-0.5 block text-[10px] text-vpv-text-muted">
                Jornada
              </label>
              <input
                type="number"
                value={manualMatchday}
                onChange={(e) => setManualMatchday(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  fetchMatchday(Number(manualSeason), Number(manualMatchday))
                }
                className="w-16 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-sm text-vpv-text"
              />
            </div>
            <button
              onClick={() =>
                fetchMatchday(Number(manualSeason), Number(manualMatchday))
              }
              className="rounded border border-vpv-accent px-2.5 py-1 text-xs font-medium text-vpv-accent hover:bg-vpv-accent/10"
            >
              Buscar
            </button>
            <div className="h-5 w-px bg-vpv-border" />
            <button
              onClick={handleScrapeMatchday}
              disabled={actionLoading !== null}
              className="rounded bg-vpv-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-vpv-accent/80 disabled:opacity-50"
            >
              {actionLoading === "scrape" ? "Scrapeando..." : "Scrapear jornada"}
            </button>
            {abortController && (
              <button
                onClick={() => abortController.abort()}
                className="rounded bg-red-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-red-700"
              >
                Cancelar
              </button>
            )}
            <button
              onClick={handleCalendar}
              disabled={actionLoading !== null}
              className="rounded border border-vpv-border px-2.5 py-1 text-xs text-vpv-text-muted hover:text-vpv-text disabled:opacity-50"
            >
              {actionLoading === "calendar" ? "..." : "Calendario"}
            </button>
          </div>

          {scrapeResult && (
            <div className="rounded bg-vpv-bg px-3 py-2 text-xs text-vpv-text whitespace-pre-line">
              {scrapeResult}
            </div>
          )}
        </div>

        {/* Match list */}
        {matchdayDetail && (
          <div className="border-t border-vpv-border">
            <div className="flex items-center justify-between px-4 py-2">
              <span className="text-xs font-medium text-vpv-text">
                J{matchdayDetail.number} — {playedCount}/
                {matchdayDetail.matches.length} jugados
              </span>
              {matchdayDetail.stats_ok && (
                <span className="rounded bg-green-500/20 px-1.5 py-0.5 text-[10px] text-green-400">
                  Stats OK
                </span>
              )}
            </div>
            <div className="divide-y divide-vpv-border/50">
              {matchdayDetail.matches.map((match) => (
                <div key={match.id}>
                  <div className="flex items-center gap-2 px-4 py-1.5">
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        match.stats_ok
                          ? "bg-green-500"
                          : match.home_score !== null
                            ? "bg-yellow-500 animate-pulse"
                            : "bg-vpv-border"
                      }`}
                    />
                    <span className="flex-1 text-xs text-vpv-text">
                      {match.home_team} vs {match.away_team}
                    </span>
                    {match.home_score !== null && (
                      <span className="text-xs font-medium text-vpv-text tabular-nums">
                        {match.home_score}-{match.away_score}
                      </span>
                    )}
                    <span className="hidden w-36 text-right text-[10px] text-vpv-text-muted sm:inline">
                      {formatMatchDate(match.played_at)}
                    </span>
                    {!match.counts && (
                      <span className="rounded bg-yellow-500/20 px-1 py-0.5 text-[9px] text-yellow-400">
                        NC
                      </span>
                    )}
                    <button
                      onClick={() => {
                        const set = new Set(expandedLogs);
                        if (set.has(match.id)) {
                          set.delete(match.id);
                          setExpandedLogs(set);
                        } else {
                          set.add(match.id);
                          setExpandedLogs(set);
                          fetchMatchLogs(match.id);
                        }
                      }}
                      className="rounded border border-vpv-border px-1.5 py-0.5 text-[10px] text-vpv-text-muted hover:text-vpv-text"
                    >
                      {expandedLogs.has(match.id) ? "Ocultar" : "Logs"}
                    </button>
                    {scrapingMatchId === match.id ? (
                      <button
                        onClick={() => abortController?.abort()}
                        className="rounded bg-red-600 px-1.5 py-0.5 text-[10px] font-medium text-white"
                      >
                        Cancelar
                      </button>
                    ) : (
                      <button
                        onClick={() => handleScrapeMatch(match.id)}
                        disabled={scrapingMatchId !== null || actionLoading !== null}
                        className="rounded border border-vpv-border px-1.5 py-0.5 text-[10px] text-vpv-text-muted hover:border-vpv-accent hover:text-vpv-accent disabled:opacity-40"
                      >
                        Scrapear
                      </button>
                    )}
                  </div>

                  {/* Inline logs */}
                  {expandedLogs.has(match.id) && (
                    <div className="bg-vpv-bg/30 px-4 py-1.5">
                      {scrapingMatchId === match.id && (
                        <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-vpv-accent" />
                      )}
                      {(matchLogs[match.id] ?? []).length === 0 ? (
                        <p className="text-[10px] text-vpv-text-muted">
                          {scrapingMatchId === match.id
                            ? "Esperando logs..."
                            : "Sin logs"}
                        </p>
                      ) : (
                        <div className="max-h-56 space-y-px overflow-y-auto">
                          {(matchLogs[match.id] ?? []).map((log) => (
                            <div
                              key={log.id}
                              className={`flex items-start gap-1.5 rounded px-1.5 py-0.5 text-[10px] ${
                                log.status === "error" ? "bg-red-500/10" : ""
                              }`}
                            >
                              {log.created_at && (
                                <span className="mt-px shrink-0 font-mono text-vpv-text-muted/50">
                                  {formatTime(log.created_at)}
                                </span>
                              )}
                              <span
                                className={`mt-px shrink-0 rounded px-1 text-[8px] font-bold uppercase ${
                                  STATUS_BADGE[log.status] ?? ""
                                }`}
                              >
                                {log.status}
                              </span>
                              <span
                                className={
                                  log.status === "error"
                                    ? "text-red-400"
                                    : "text-vpv-text-muted"
                                }
                              >
                                {log.message}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Log history (grouped by match) ── */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <button
          type="button"
          onClick={() => setShowDbLogs((p) => !p)}
          className="flex w-full items-center justify-between px-4 py-2.5"
        >
          <h2 className="text-sm font-semibold text-vpv-text">
            Historial de logs
          </h2>
          <span className="text-xs text-vpv-text-muted">
            {showDbLogs ? "\u25B2" : "\u25BC"}
          </span>
        </button>

        {showDbLogs && (
          <div className="border-t border-vpv-border">
            {/* Filters */}
            <div className="flex flex-wrap items-end gap-2 px-4 py-2">
              <div>
                <label className="mb-0.5 block text-[9px] text-vpv-text-muted">
                  Jornada
                </label>
                <input
                  type="number"
                  value={logMatchday}
                  onChange={(e) => setLogMatchday(e.target.value)}
                  placeholder="Todas"
                  className="w-16 rounded border border-vpv-border bg-vpv-bg px-1.5 py-1 text-xs text-vpv-text"
                />
              </div>
              <div>
                <label className="mb-0.5 block text-[9px] text-vpv-text-muted">
                  Tipo
                </label>
                <div className="flex gap-0.5">
                  {[
                    { value: "", label: "Todos" },
                    { value: "match", label: "Manual" },
                    { value: "matchday", label: "Jornada" },
                    { value: "scheduler", label: "Auto" },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setLogJobType(opt.value)}
                      className={`rounded px-2 py-1 text-[10px] font-medium ${
                        logJobType === opt.value
                          ? "bg-vpv-accent text-white"
                          : "border border-vpv-border text-vpv-text-muted"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <button
                onClick={fetchLogSummary}
                className="rounded bg-vpv-accent/10 px-2 py-1 text-[10px] font-medium text-vpv-accent hover:bg-vpv-accent/20"
              >
                Actualizar
              </button>
              <span className="text-[10px] text-vpv-text-muted">
                {logSummary.length} partidos
              </span>
            </div>

            {/* Grouped entries */}
            <div className="max-h-96 divide-y divide-vpv-border/30 overflow-y-auto">
              {logSummary.map((s) => (
                <div key={`${s.matchday_number}-${s.match_id}`}>
                  <button
                    type="button"
                    onClick={() => {
                      if (expandedLogMatch === s.match_id) {
                        setExpandedLogMatch(null);
                      } else {
                        setExpandedLogMatch(s.match_id);
                        if (s.match_id) fetchMatchLogEntries(s.match_id);
                      }
                    }}
                    className="flex w-full items-center gap-2 px-4 py-1.5 text-left hover:bg-vpv-bg/30"
                  >
                    <span className="text-[10px] text-vpv-text-muted">
                      J{s.matchday_number}
                    </span>
                    <span className="flex-1 text-xs font-medium text-vpv-text">
                      {s.match_label ?? `Match #${s.match_id}`}
                    </span>
                    <span className="text-[10px] text-green-400">
                      {s.ok}
                    </span>
                    {s.skip > 0 && (
                      <span className="text-[10px] text-amber-400">
                        {s.skip}
                      </span>
                    )}
                    {s.error > 0 && (
                      <span className="text-[10px] font-bold text-red-400">
                        {s.error}
                      </span>
                    )}
                    <span className="text-[9px] text-vpv-text-muted/50">
                      {s.last_at ? formatRelative(s.last_at) : ""}
                    </span>
                    <span className="text-[10px] text-vpv-text-muted">
                      {expandedLogMatch === s.match_id ? "\u25B2" : "\u25BC"}
                    </span>
                  </button>

                  {/* Expanded: per-player logs */}
                  {expandedLogMatch === s.match_id && (
                    <div className="max-h-60 overflow-y-auto bg-vpv-bg/20 px-4 py-1">
                      {expandedLogEntries.length === 0 ? (
                        <p className="py-2 text-[10px] text-vpv-text-muted">
                          Cargando...
                        </p>
                      ) : (
                        expandedLogEntries.map((log) => (
                          <div
                            key={log.id}
                            className={`flex items-start gap-1.5 py-0.5 text-[10px] ${
                              log.status === "error" ? "text-red-400" : "text-vpv-text-muted"
                            }`}
                          >
                            {log.created_at && (
                              <span className="mt-px shrink-0 font-mono text-vpv-text-muted/50">
                                {formatTime(log.created_at)}
                              </span>
                            )}
                            <span
                              className={`mt-px shrink-0 rounded px-1 text-[8px] font-bold uppercase ${
                                STATUS_BADGE[log.status] ?? ""
                              }`}
                            >
                              {log.status}
                            </span>
                            <span className="min-w-0 flex-1">{log.message}</span>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))}
              {logSummary.length === 0 && (
                <p className="px-4 py-4 text-center text-xs text-vpv-text-muted">
                  Sin logs
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
