"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import type {
  CompetitionDetail,
  CompetitionListResponse,
  CompetitionSummary,
  FormatInfo,
} from "@/types";

interface PlayoffsCardProps {
  seasonId: number;
  matchdayStart: number;
  matchdayEnd: number | null;
}

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente",
  regular: "Fase regular",
  ko: "Eliminatorias",
  completed: "Finalizado",
};

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-zinc-500/15 text-zinc-300",
  regular: "bg-blue-500/15 text-blue-300",
  ko: "bg-amber-500/15 text-amber-300",
  completed: "bg-emerald-500/15 text-emerald-300",
};

export function PlayoffsCard({ seasonId, matchdayStart, matchdayEnd }: PlayoffsCardProps) {
  const [formats, setFormats] = useState<FormatInfo[]>([]);
  const [selectedFormat, setSelectedFormat] = useState<string>("");
  const [playoff, setPlayoff] = useState<CompetitionSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  // Inputs for start_regular / start_ko
  const [regularStart, setRegularStart] = useState<string>(String(matchdayStart));
  const [regularEnd, setRegularEnd] = useState<string>(
    String(Math.min((matchdayEnd ?? matchdayStart + 5), matchdayStart + 5)),
  );
  const [koMatchdays, setKoMatchdays] = useState<string>(""); // CSV

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [formatList, comps] = await Promise.all([
        apiClient.get<FormatInfo[]>("/competitions/formats"),
        apiClient.get<CompetitionListResponse>(`/competitions/season/${seasonId}`),
      ]);
      setFormats(formatList);
      if (formatList.length > 0 && !selectedFormat) {
        setSelectedFormat(formatList[0].format_id);
      }
      const existing = comps.competitions.find((c) => c.type === "playoff") ?? null;
      setPlayoff(existing);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando playoff");
    } finally {
      setLoading(false);
    }
  }, [seasonId, selectedFormat]);

  useEffect(() => {
    load();
  }, [load]);

  const currentFormat = formats.find((f) => f.format_id === selectedFormat);

  async function handleCreate() {
    if (!selectedFormat) return;
    setBusy("create");
    setError(null);
    try {
      const comp = await apiClient.post<CompetitionDetail>(
        `/competitions/admin/season/${seasonId}`,
        { format_id: selectedFormat },
      );
      setPlayoff({
        id: comp.id,
        season_id: comp.season_id,
        name: comp.name,
        type: comp.type,
        status: comp.status,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando el playoff");
    } finally {
      setBusy(null);
    }
  }

  async function handleStartRegular() {
    if (!playoff) return;
    const start = Number(regularStart);
    const end = Number(regularEnd);
    if (!Number.isFinite(start) || !Number.isFinite(end)) {
      setError("Las jornadas deben ser números");
      return;
    }
    setBusy("regular");
    setError(null);
    try {
      await apiClient.post(`/competitions/admin/${playoff.id}/start-regular`, {
        matchday_start: start,
        matchday_end: end,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error generando la fase regular");
    } finally {
      setBusy(null);
    }
  }

  async function handleStartKo() {
    if (!playoff) return;
    const numbers = koMatchdays
      .split(",")
      .map((s) => Number(s.trim()))
      .filter((n) => Number.isFinite(n));
    if (numbers.length === 0) {
      setError("Indica al menos una jornada KO");
      return;
    }
    setBusy("ko");
    setError(null);
    try {
      await apiClient.post(`/competitions/admin/${playoff.id}/start-ko`, {
        ko_matchday_numbers: numbers,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error iniciando las eliminatorias");
    } finally {
      setBusy(null);
    }
  }

  const status = playoff?.status ?? "missing";

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-vpv-text">Playoffs</h3>
        {playoff && (
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
              STATUS_COLOR[status] ?? "bg-zinc-500/15 text-zinc-300"
            }`}
          >
            {STATUS_LABEL[status] ?? status}
          </span>
        )}
      </div>

      {loading && <p className="text-xs text-vpv-text-muted">Cargando…</p>}

      {error && (
        <div className="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {!loading && !playoff && (
        <div className="space-y-3">
          <p className="text-xs text-vpv-text-muted">
            Aún no hay playoff configurado para esta temporada.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs text-vpv-text-muted">Formato:</label>
            <select
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value)}
              className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
            >
              {formats.map((f) => (
                <option key={f.format_id} value={f.format_id}>
                  {f.display_name}
                </option>
              ))}
            </select>
            <button
              onClick={handleCreate}
              disabled={!selectedFormat || busy === "create"}
              className="rounded bg-vpv-accent px-3 py-1 text-xs font-medium text-vpv-bg transition-opacity disabled:opacity-40"
            >
              {busy === "create" ? "Creando…" : "Crear Playoff"}
            </button>
          </div>
          {currentFormat && (
            <p className="text-[11px] text-vpv-text-muted/70">
              {currentFormat.n_rounds_regular} jornadas RR ·{" "}
              {currentFormat.n_rounds_ko} jornadas KO.
            </p>
          )}
        </div>
      )}

      {playoff && status === "pending" && (
        <div className="space-y-2">
          <p className="text-xs text-vpv-text-muted">
            Define el rango de jornadas para la fase regular.
            {currentFormat &&
              ` El formato requiere ${currentFormat.n_rounds_regular} jornadas.`}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs">
              Jornada inicio
              <input
                type="number"
                value={regularStart}
                onChange={(e) => setRegularStart(e.target.value)}
                className="ml-2 w-16 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
              />
            </label>
            <label className="text-xs">
              Jornada fin
              <input
                type="number"
                value={regularEnd}
                onChange={(e) => setRegularEnd(e.target.value)}
                className="ml-2 w-16 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
              />
            </label>
            <button
              onClick={handleStartRegular}
              disabled={busy === "regular"}
              className="rounded bg-vpv-accent px-3 py-1 text-xs font-medium text-vpv-bg transition-opacity disabled:opacity-40"
            >
              {busy === "regular" ? "Generando…" : "Generar fase regular"}
            </button>
          </div>
        </div>
      )}

      {playoff && status === "regular" && (
        <div className="space-y-2">
          <p className="text-xs text-vpv-text-muted">
            Fase regular en curso. Cuando todos los cruces estén resueltos podrás
            iniciar las eliminatorias.
            {currentFormat &&
              ` El KO necesita ${currentFormat.n_rounds_ko} jornadas (números separados por coma).`}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs">
              Jornadas KO
              <input
                type="text"
                placeholder="ej: 7,8"
                value={koMatchdays}
                onChange={(e) => setKoMatchdays(e.target.value)}
                className="ml-2 w-28 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
              />
            </label>
            <button
              onClick={handleStartKo}
              disabled={busy === "ko"}
              className="rounded bg-vpv-accent px-3 py-1 text-xs font-medium text-vpv-bg transition-opacity disabled:opacity-40"
            >
              {busy === "ko" ? "Iniciando…" : "Iniciar eliminatorias"}
            </button>
          </div>
        </div>
      )}

      {playoff && (status === "ko" || status === "completed") && (
        <p className="text-xs text-vpv-text-muted">
          {status === "completed"
            ? "Playoff finalizado."
            : "Eliminatorias en curso."}{" "}
          <a
            href="/playoffs"
            className="text-vpv-accent underline-offset-2 hover:underline"
          >
            Ver detalle público
          </a>
          .
        </p>
      )}
    </div>
  );
}
