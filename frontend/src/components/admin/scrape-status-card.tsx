"use client";

import { type ReactNode, useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";

interface ScrapeStatus {
  season_id: number;
  teams: number;
  players_total: number;
  players_with_position: number;
  players_with_photo: number;
  matchdays_total: number;
  matchdays_counting: number;
  matchdays_with_fixtures: number;
  matches_total: number;
  matches_with_result: number;
  first_match_at: string | null;
  last_match_at: string | null;
  last_import_at: string | null;
  last_import_status: string | null;
  last_import_message: string | null;
  last_import_detail: Record<string, number> | null;
}

type State = "ok" | "warn" | "empty";

function dot(state: State): string {
  return state === "ok"
    ? "bg-emerald-500"
    : state === "warn"
      ? "bg-amber-500"
      : "bg-zinc-600";
}

function Row({
  label,
  state,
  children,
}: {
  label: string;
  state: State;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-vpv-border/50 py-1.5 text-xs first:border-t-0">
      <span className="flex items-center gap-2 text-vpv-text-muted">
        <span className={`h-2 w-2 shrink-0 rounded-full ${dot(state)}`} />
        {label}
      </span>
      <span className="text-right tabular-nums text-vpv-text">{children}</span>
    </div>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ScrapeStatusCard({ seasonId }: { seasonId: number }) {
  const [status, setStatus] = useState<ScrapeStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(
        await apiClient.get<ScrapeStatus>(`/seasons/admin/${seasonId}/scrape-status`),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando estado");
    } finally {
      setLoading(false);
    }
  }, [seasonId]);

  useEffect(() => {
    load();
  }, [load]);

  async function reimport() {
    if (!confirm("Re-importar equipos, plantillas y calendario? Corre en segundo plano.")) return;
    setBusy("reimport");
    setNote(null);
    setError(null);
    try {
      await apiClient.post(`/seasons/admin/${seasonId}/reimport`, {});
      setNote("Import lanzado en segundo plano. Pulsa Actualizar en unos segundos.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error lanzando el import");
    } finally {
      setBusy(null);
    }
  }

  async function syncCalendar() {
    setBusy("calendar");
    setNote(null);
    setError(null);
    try {
      const res = await apiClient.post<Record<string, number>>(
        `/scraping/calendar/${seasonId}`,
        {},
      );
      setNote(
        `Calendario sincronizado: ${res.matches_created ?? 0} creados, ` +
          `${res.dates_updated ?? 0} fechas, ${res.scores_updated ?? 0} resultados.`,
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error sincronizando calendario");
    } finally {
      setBusy(null);
    }
  }

  const s = status;
  const teamsState: State = !s || s.teams === 0 ? "empty" : "ok";
  const squadState: State = !s || s.players_total === 0
    ? "empty"
    : s.players_with_position < s.players_total
      ? "warn"
      : "ok";
  const photoState: State = !s || s.players_total === 0
    ? "empty"
    : s.players_with_photo < s.players_total
      ? "warn"
      : "ok";
  const calState: State = !s || s.matches_total === 0
    ? "empty"
    : s.matchdays_with_fixtures < s.matchdays_total
      ? "warn"
      : "ok";

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-vpv-text">Estado de scraping</h3>
        <button
          onClick={load}
          disabled={loading}
          className="rounded bg-vpv-bg px-2.5 py-1 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
        >
          {loading ? "…" : "Actualizar"}
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {s && (
        <div className="mb-3">
          <Row label="Equipos" state={teamsState}>
            {s.teams}
          </Row>
          <Row label="Plantillas · con posición" state={squadState}>
            {s.players_with_position}/{s.players_total}
          </Row>
          <Row label="Fotos" state={photoState}>
            {s.players_with_photo}/{s.players_total}
          </Row>
          <Row label="Calendario · jornadas con partidos" state={calState}>
            {s.matchdays_with_fixtures}/{s.matchdays_total}
          </Row>
          <Row label="Partidos · con resultado" state={calState}>
            {s.matches_with_result}/{s.matches_total}
          </Row>

          <div className="mt-2 border-t border-vpv-border/50 pt-2 text-[11px] text-vpv-text-muted">
            Último import:{" "}
            {s.last_import_at ? (
              <span
                className={
                  s.last_import_status === "error"
                    ? "text-red-400"
                    : "text-emerald-400"
                }
              >
                {fmtDate(s.last_import_at)} · {s.last_import_message ?? s.last_import_status}
              </span>
            ) : (
              <span className="text-vpv-text-muted/70">nunca</span>
            )}
          </div>
        </div>
      )}

      {note && (
        <div className="mb-3 rounded border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-xs text-blue-300">
          {note}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={reimport}
          disabled={busy !== null}
          className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
        >
          {busy === "reimport" ? "Lanzando…" : "Re-importar equipos"}
        </button>
        <button
          onClick={syncCalendar}
          disabled={busy !== null}
          className="rounded bg-vpv-bg px-3 py-1.5 text-xs font-medium text-vpv-text transition-colors hover:bg-vpv-border disabled:opacity-50"
        >
          {busy === "calendar" ? "Sincronizando…" : "Sincronizar calendario"}
        </button>
      </div>
    </div>
  );
}
