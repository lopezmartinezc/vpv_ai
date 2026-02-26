"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface SchedulerStatus {
  running: boolean;
  poll_interval_seconds: number;
  last_tick_at: string | null;
  next_run_at: string | null;
  lock_held: boolean;
  last_calendar_sync_at: string | null;
  next_calendar_sync_at: string | null;
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

export default function AdminScrapingPage() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [scrapeResult, setScrapeResult] = useState<string | null>(null);

  // Current matchday data
  const [season, setSeason] = useState<SeasonSummary | null>(null);
  const [matchdayDetail, setMatchdayDetail] = useState<MatchdayDetail | null>(
    null,
  );

  // Manual scraping overrides
  const [manualSeason, setManualSeason] = useState("");
  const [manualMatchday, setManualMatchday] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiClient.get<SchedulerStatus>(
        "/scraping/admin/status",
      );
      setStatus(data);
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCurrentMatchday = useCallback(async () => {
    try {
      const currentSeason = await apiClient.get<SeasonSummary>(
        "/seasons/current",
      );
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

  async function handleAction(action: "start" | "stop" | "trigger") {
    setActionLoading(action);
    try {
      const data = await apiClient.post<
        SchedulerStatus | { triggered: boolean }
      >(`/scraping/admin/${action}`, {});
      if ("running" in data) {
        setStatus(data as SchedulerStatus);
      } else {
        await fetchStatus();
      }
    } catch {
      // error
    } finally {
      setActionLoading(null);
    }
  }

  async function handleManualScrape() {
    setActionLoading("scrape");
    setScrapeResult(null);
    try {
      const data = await apiClient.post<Record<string, number>>(
        `/scraping/matchday/${manualSeason}/${manualMatchday}`,
        {},
      );
      setScrapeResult(
        `Procesados: ${data.processed ?? 0}, Saltados: ${data.skipped ?? 0}, Errores: ${data.errors ?? 0}`,
      );
      await fetchStatus();
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

  return (
    <div className="space-y-4">
      {/* Scheduler Status */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Scheduler automatico
          </h2>
        </div>
        <div className="space-y-3 px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span
                className={`h-3 w-3 rounded-full ${status?.running ? "bg-green-500" : "bg-red-500"}`}
              />
              <span className="text-sm font-medium text-vpv-text">
                {status?.running ? "Activo" : "Detenido"}
              </span>
            </div>
            {status?.lock_held && (
              <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs font-medium text-yellow-400">
                Tick en curso
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            <div>
              <p className="text-vpv-text-muted">Intervalo stats</p>
              <p className="font-medium text-vpv-text">
                {status?.poll_interval_seconds
                  ? `${Math.floor(status.poll_interval_seconds / 60)} min`
                  : "\u2014"}
              </p>
            </div>
            <div>
              <p className="text-vpv-text-muted">Ultimo tick</p>
              <p className="font-medium text-vpv-text">
                {formatDateTime(status?.last_tick_at ?? null)}
              </p>
            </div>
            <div>
              <p className="text-vpv-text-muted">Proximo tick</p>
              <p className="font-medium text-vpv-text">
                {formatDateTime(status?.next_run_at ?? null)}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            <div>
              <p className="text-vpv-text-muted">Sync calendario</p>
              <p className="font-medium text-vpv-text">Diario 06:00 UTC</p>
            </div>
            <div>
              <p className="text-vpv-text-muted">Ultimo sync</p>
              <p className="font-medium text-vpv-text">
                {formatDateTime(status?.last_calendar_sync_at ?? null)}
              </p>
            </div>
            <div>
              <p className="text-vpv-text-muted">Proximo sync</p>
              <p className="font-medium text-vpv-text">
                {formatDateTime(status?.next_calendar_sync_at ?? null)}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            {status?.running ? (
              <button
                onClick={() => handleAction("stop")}
                disabled={actionLoading !== null}
                className="rounded bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {actionLoading === "stop" ? "Deteniendo..." : "Detener"}
              </button>
            ) : (
              <button
                onClick={() => handleAction("start")}
                disabled={actionLoading !== null}
                className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
              >
                {actionLoading === "start" ? "Iniciando..." : "Iniciar"}
              </button>
            )}
            <button
              onClick={() => handleAction("trigger")}
              disabled={actionLoading !== null || !status?.running}
              className="rounded border border-vpv-border px-3 py-1.5 text-xs font-medium text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
            >
              {actionLoading === "trigger"
                ? "Ejecutando..."
                : "Forzar tick ahora"}
            </button>
          </div>
        </div>
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
              return (
                <div
                  key={match.id}
                  className="flex items-center gap-3 px-4 py-2"
                >
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
            <div className="rounded bg-vpv-bg px-3 py-2 text-sm text-vpv-text">
              {scrapeResult}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
