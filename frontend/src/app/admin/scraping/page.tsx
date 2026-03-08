"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface LogEntry {
  ts: string;
  level: string;
  msg: string;
}

interface JobStatus {
  id: string;
  name: string;
  type: "interval" | "cron";
  interval_seconds?: number;
  schedule?: string;
  last_run_at: string | null;
  next_run_at: string | null;
  lock_held?: boolean;
  logs?: LogEntry[];
}

interface SchedulerStatus {
  running: boolean;
  poll_interval_seconds: number;
  last_tick_at: string | null;
  next_run_at: string | null;
  lock_held: boolean;
  last_calendar_sync_at: string | null;
  next_calendar_sync_at: string | null;
  jobs: JobStatus[];
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

function formatDateTime(iso: string | null): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return d.toLocaleString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatRelative(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const absDiffMs = Math.abs(diffMs);

  if (absDiffMs < 60_000) return diffMs < 0 ? "hace <1 min" : "en <1 min";

  const mins = Math.floor(absDiffMs / 60_000);
  if (mins < 60) return diffMs < 0 ? `hace ${mins} min` : `en ${mins} min`;

  const hours = Math.floor(mins / 60);
  if (hours < 24) return diffMs < 0 ? `hace ${hours}h` : `en ${hours}h`;

  const days = Math.floor(hours / 24);
  return diffMs < 0 ? `hace ${days}d` : `en ${days}d`;
}

function formatMatchDate(iso: string | null): string {
  if (!iso) return "Sin fecha";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffH = Math.round(diffMs / (1000 * 60 * 60));

  const dateStr = d.toLocaleString("es-ES", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

  if (diffMs < 0) return `${dateStr} (jugado)`;
  if (diffH < 24) return `${dateStr} (en ${diffH}h)`;
  return dateStr;
}

function matchStatus(match: MatchEntry): "played" | "live" | "upcoming" {
  if (match.home_score !== null) return "played";
  if (!match.played_at) return "upcoming";
  const d = new Date(match.played_at);
  const now = new Date();
  if (d.getTime() <= now.getTime()) return "live";
  return "upcoming";
}

const JOB_TRIGGER_MAP: Record<string, string> = {
  scraping_tick: "/scraping/admin/trigger",
  calendar_sync: "/scraping/admin/trigger/calendar-sync",
  deadline_check: "/scraping/admin/trigger/deadline-check",
};

const JOB_ICONS: Record<string, string> = {
  scraping_tick: "M",
  calendar_sync: "C",
  deadline_check: "D",
};

function formatFrequency(job: JobStatus): string {
  if (job.type === "cron" && job.schedule) return job.schedule;
  if (job.interval_seconds) {
    if (job.interval_seconds >= 60) return `Cada ${Math.floor(job.interval_seconds / 60)} min`;
    return `Cada ${job.interval_seconds}s`;
  }
  return "\u2014";
}

const LOG_LEVEL_COLORS: Record<string, string> = {
  info: "text-vpv-text-muted",
  warning: "text-yellow-400",
  error: "text-red-400",
};

function formatLogTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function JobCard({
  job,
  schedulerRunning,
  onTrigger,
  triggeringJob,
}: {
  job: JobStatus;
  schedulerRunning: boolean;
  onTrigger: (jobId: string) => void;
  triggeringJob: string | null;
}) {
  const [showLogs, setShowLogs] = useState(false);
  const isTriggering = triggeringJob === job.id;
  const logs = job.logs ?? [];
  const lastLogs = logs.slice(-15);

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-center justify-between border-b border-vpv-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-vpv-accent/15 text-xs font-bold text-vpv-accent">
            {JOB_ICONS[job.id] ?? "?"}
          </span>
          <div>
            <h3 className="text-sm font-semibold text-vpv-text">{job.name}</h3>
            <p className="text-[11px] text-vpv-text-muted">{formatFrequency(job)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {job.lock_held && (
            <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-[10px] font-medium text-yellow-400">
              En curso
            </span>
          )}
          <button
            onClick={() => onTrigger(job.id)}
            disabled={!schedulerRunning || triggeringJob !== null}
            className="rounded bg-vpv-accent/10 px-2.5 py-1 text-[11px] font-medium text-vpv-accent transition-colors hover:bg-vpv-accent/20 disabled:opacity-40"
          >
            {isTriggering ? "Ejecutando..." : "Forzar"}
          </button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 px-4 py-2.5 text-xs">
        <div>
          <p className="text-vpv-text-muted">Ultima ejecucion</p>
          <p className="font-medium text-vpv-text">{formatDateTime(job.last_run_at)}</p>
          {job.last_run_at && (
            <p className="text-[10px] text-vpv-text-muted">{formatRelative(job.last_run_at)}</p>
          )}
        </div>
        <div>
          <p className="text-vpv-text-muted">Proxima ejecucion</p>
          <p className="font-medium text-vpv-text">{formatDateTime(job.next_run_at)}</p>
          {job.next_run_at && (
            <p className="text-[10px] text-vpv-text-muted">{formatRelative(job.next_run_at)}</p>
          )}
        </div>
      </div>

      {/* Log section */}
      {logs.length > 0 && (
        <div className="border-t border-vpv-border">
          <button
            type="button"
            onClick={() => setShowLogs((p) => !p)}
            className="flex w-full items-center justify-between px-4 py-1.5 text-[11px] text-vpv-text-muted transition-colors hover:text-vpv-text"
          >
            <span>Log ({logs.length})</span>
            <svg
              className={`h-3 w-3 transition-transform ${showLogs ? "rotate-180" : ""}`}
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          {showLogs && (
            <div className="max-h-48 overflow-y-auto border-t border-vpv-border/50 bg-vpv-bg/50 px-3 py-1.5 font-mono text-[10px] leading-relaxed">
              {lastLogs.map((entry, i) => (
                <div key={i} className="flex gap-2">
                  <span className="shrink-0 text-vpv-text-muted/60">{formatLogTime(entry.ts)}</span>
                  <span className={LOG_LEVEL_COLORS[entry.level] ?? "text-vpv-text-muted"}>
                    {entry.msg}
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

export default function AdminScrapingPage() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [triggeringJob, setTriggeringJob] = useState<string | null>(null);
  const [scrapeResult, setScrapeResult] = useState<string | null>(null);

  // Current matchday data
  const [season, setSeason] = useState<SeasonSummary | null>(null);
  const [matchdayDetail, setMatchdayDetail] = useState<MatchdayDetail | null>(null);

  // Manual scraping overrides
  const [manualSeason, setManualSeason] = useState("");
  const [manualMatchday, setManualMatchday] = useState("");
  const [scrapingMatchId, setScrapingMatchId] = useState<number | null>(null);
  const [matchScrapeResult, setMatchScrapeResult] = useState<{
    matchId: number;
    lines: string[];
  } | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiClient.get<SchedulerStatus>("/scraping/admin/status");
      setStatus(data);
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCurrentMatchday = useCallback(async () => {
    try {
      const currentSeason = await apiClient.get<SeasonSummary>("/seasons/current");
      setSeason(currentSeason);
      setManualSeason(String(currentSeason.id));
      setManualMatchday(String(currentSeason.matchday_current));

      if (currentSeason.matchday_current > 0) {
        const detail = await apiClient.get<MatchdayDetail>(
          `/matchdays/${currentSeason.id}/${currentSeason.matchday_current}`,
        );
        setMatchdayDetail(detail);
      }
    } catch {
      // no active season
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchCurrentMatchday();
    const interval = setInterval(fetchStatus, 10_000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchCurrentMatchday]);

  async function handleAction(action: "start" | "stop") {
    setActionLoading(action);
    try {
      const data = await apiClient.post<SchedulerStatus>(`/scraping/admin/${action}`, {});
      setStatus(data);
    } catch {
      // error
    } finally {
      setActionLoading(null);
    }
  }

  async function handleTriggerJob(jobId: string) {
    const endpoint = JOB_TRIGGER_MAP[jobId];
    if (!endpoint) return;

    setTriggeringJob(jobId);
    try {
      await apiClient.post(endpoint, {});
      // Give the job a moment to start, then refresh status + matchday
      setTimeout(() => {
        fetchStatus();
        fetchCurrentMatchday();
      }, 1500);
    } catch {
      // error
    } finally {
      setTriggeringJob(null);
    }
  }

  async function handleManualScrape() {
    setActionLoading("scrape");
    setScrapeResult(null);
    try {
      const data = await apiClient.post<{
        processed?: number;
        skipped?: number;
        errors?: number;
        error_details?: string[];
      }>(`/scraping/matchday/${manualSeason}/${manualMatchday}`, {});
      const errors = data.errors ?? 0;
      const details = data.error_details ?? [];
      let msg = `Procesados: ${data.processed ?? 0}, Saltados: ${data.skipped ?? 0}, Errores: ${errors}`;
      if (details.length > 0) {
        msg += "\n" + details.join("\n");
      }
      setScrapeResult(msg);
      await Promise.all([fetchStatus(), fetchCurrentMatchday()]);
    } catch {
      setScrapeResult("Error al ejecutar scraping");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleCalendarScrape() {
    setActionLoading("calendar");
    setScrapeResult(null);
    try {
      const data = await apiClient.post<Record<string, number>>(
        `/scraping/calendar/${manualSeason}`,
        {},
      );
      setScrapeResult(
        `Resultados actualizados: ${data.scores_updated ?? 0}, Fechas actualizadas: ${data.dates_updated ?? 0}`,
      );
      await fetchCurrentMatchday();
    } catch {
      setScrapeResult("Error al actualizar calendario");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleScrapeMatch(matchId: number) {
    if (!season || !matchdayDetail) return;
    setScrapingMatchId(matchId);
    setMatchScrapeResult(null);
    try {
      const data = await apiClient.post<{
        processed?: number;
        skipped?: number;
        errors?: number;
        error_details?: string[];
      }>(
        `/scraping/match/${season.id}/${matchdayDetail.number}/${matchId}`,
        {},
      );
      const errors = data.errors ?? 0;
      const details = data.error_details ?? [];
      const lines = [
        `Procesados: ${data.processed ?? 0}, Saltados: ${data.skipped ?? 0}, Errores: ${errors}`,
        ...details,
      ];
      setMatchScrapeResult({ matchId, lines });
      await fetchCurrentMatchday();
    } catch {
      setMatchScrapeResult({ matchId, lines: ["Error al scrapear partido"] });
    } finally {
      setScrapingMatchId(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 py-4">
        <div className="h-32 animate-pulse rounded-lg bg-vpv-border" />
        <div className="h-48 animate-pulse rounded-lg bg-vpv-border" />
      </div>
    );
  }

  const playedCount =
    matchdayDetail?.matches.filter((m) => m.home_score !== null).length ?? 0;
  const totalCount = matchdayDetail?.matches.length ?? 0;
  const jobs = status?.jobs ?? [];

  return (
    <div className="space-y-4">
      {/* Scheduler Global Controls */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span
              className={`h-3 w-3 rounded-full ${status?.running ? "bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]" : "bg-red-500"}`}
            />
            <h2 className="font-semibold text-vpv-text">
              Tareas programadas
            </h2>
            <span className="text-xs text-vpv-text-muted">
              {status?.running ? "Scheduler activo" : "Scheduler detenido"}
            </span>
          </div>
          <div className="flex gap-2">
            {status?.running ? (
              <button
                onClick={() => handleAction("stop")}
                disabled={actionLoading !== null}
                className="rounded bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {actionLoading === "stop" ? "Deteniendo..." : "Detener todo"}
              </button>
            ) : (
              <button
                onClick={() => handleAction("start")}
                disabled={actionLoading !== null}
                className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
              >
                {actionLoading === "start" ? "Iniciando..." : "Iniciar todo"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Per-Job Cards */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            schedulerRunning={status?.running ?? false}
            onTrigger={handleTriggerJob}
            triggeringJob={triggeringJob}
          />
        ))}
      </div>

      {/* Current Matchday Matches */}
      {matchdayDetail && season && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
          <div className="border-b border-vpv-border px-4 py-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-vpv-text">
                Jornada {matchdayDetail.number} — {season.name}
              </h2>
              <span className="text-xs text-vpv-text-muted">
                {playedCount}/{totalCount} jugados
                {matchdayDetail.stats_ok && (
                  <span className="ml-2 rounded bg-green-500/20 px-1.5 py-0.5 text-green-400">
                    Stats OK
                  </span>
                )}
              </span>
            </div>
          </div>
          <div className="divide-y divide-vpv-border">
            {matchdayDetail.matches.map((match) => {
              const st = matchStatus(match);
              const hasResult = matchScrapeResult?.matchId === match.id;
              return (
                <div key={match.id}>
                  <div className="flex items-center gap-3 px-4 py-2">
                    {/* Scraping status indicator */}
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        match.stats_ok
                          ? "bg-green-500"
                          : st === "played"
                            ? "bg-yellow-500 animate-pulse"
                            : "bg-vpv-border"
                      }`}
                      title={
                        match.stats_ok
                          ? "Stats scrapeados"
                          : st === "played"
                            ? "Pendiente de scrapear"
                            : "No jugado"
                      }
                    />
                    <div className="flex-1">
                      <span className="text-sm text-vpv-text">
                        {match.home_team} vs {match.away_team}
                      </span>
                    </div>
                    <div className="text-right">
                      {st === "played" ? (
                        <span className="text-sm font-medium text-vpv-text">
                          {match.home_score} - {match.away_score}
                        </span>
                      ) : st === "live" ? (
                        <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs font-medium text-red-400">
                          En juego
                        </span>
                      ) : null}
                    </div>
                    <div className="w-44 text-right">
                      <span
                        className={`text-xs ${
                          st === "played"
                            ? "text-vpv-text-muted"
                            : st === "live"
                              ? "text-red-400"
                              : "text-vpv-text"
                        }`}
                      >
                        {formatMatchDate(match.played_at)}
                      </span>
                    </div>
                    {!match.counts && (
                      <span className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-400">
                        NC
                      </span>
                    )}
                    <button
                      onClick={() => handleScrapeMatch(match.id)}
                      disabled={scrapingMatchId !== null || actionLoading !== null}
                      className="shrink-0 rounded border border-vpv-border px-2 py-0.5 text-[11px] text-vpv-text-muted transition-colors hover:border-vpv-accent hover:text-vpv-accent disabled:opacity-40"
                    >
                      {scrapingMatchId === match.id
                        ? "Scrapeando..."
                        : "Scrapear"}
                    </button>
                  </div>
                  {/* Inline scrape result for this match */}
                  {hasResult && matchScrapeResult && (
                    <div className="border-t border-vpv-border/30 bg-vpv-bg/40 px-4 py-1.5 pl-10">
                      {matchScrapeResult.lines.map((line, i) => (
                        <div
                          key={i}
                          className={`text-xs ${i > 0 ? "text-red-400" : "text-vpv-text-muted"}`}
                        >
                          {line}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Manual Scraping */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">Scraping manual</h2>
        </div>
        <div className="space-y-3 px-4 py-3">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs text-vpv-text-muted">
                Temporada ID
              </label>
              <input
                type="number"
                value={manualSeason}
                onChange={(e) => setManualSeason(e.target.value)}
                className="w-20 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-vpv-text-muted">
                Jornada
              </label>
              <input
                type="number"
                value={manualMatchday}
                onChange={(e) => setManualMatchday(e.target.value)}
                className="w-20 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
              />
            </div>
            <button
              onClick={handleManualScrape}
              disabled={actionLoading !== null}
              className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
            >
              {actionLoading === "scrape"
                ? "Scrapeando..."
                : "Scrapear jornada"}
            </button>
            <button
              onClick={handleCalendarScrape}
              disabled={actionLoading !== null}
              className="rounded border border-vpv-border px-3 py-1.5 text-xs font-medium text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
            >
              {actionLoading === "calendar"
                ? "Actualizando..."
                : "Actualizar calendario"}
            </button>
          </div>

          {scrapeResult && (
            <div className="rounded bg-vpv-bg px-3 py-2 text-sm text-vpv-text whitespace-pre-line">
              {scrapeResult.split("\n").map((line, i) => (
                <div
                  key={i}
                  className={
                    i > 0 ? "pl-2 text-xs text-red-400" : ""
                  }
                >
                  {line}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
