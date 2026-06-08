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
  /** Distinct playoff name within the season (e.g. "Apertura",
   *  "Clausura", or just "Playoff" for a tournament). */
  playoffName?: string;
  /** Card title shown in the header. Defaults to "Playoffs". */
  title?: string;
  /** Default format suggested in the create dropdown. */
  defaultFormatId?: string;
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

export function PlayoffsCard({
  seasonId,
  matchdayStart,
  matchdayEnd,
  playoffName,
  title = "Playoffs",
  defaultFormatId,
}: PlayoffsCardProps) {
  const [formats, setFormats] = useState<FormatInfo[]>([]);
  const [selectedFormat, setSelectedFormat] = useState<string>(defaultFormatId ?? "");
  const [playoff, setPlayoff] = useState<CompetitionSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  // Single input for the regular phase: the user only picks the
  // starting matchday. The end is derived from the selected format's
  // required_rounds_regular (so we never send an off-by-one to the
  // backend). The KO matchdays input remains free-form CSV.
  const [regularStart, setRegularStart] = useState<string>(String(matchdayStart));
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
        setSelectedFormat(defaultFormatId ?? formatList[0].format_id);
      }
      // Find this specific playoff — by name when provided, else first
      // 'playoff' competition of the season.
      const playoffComps = comps.competitions.filter((c) => c.type === "playoff");
      const existing = playoffName
        ? playoffComps.find((c) => c.name === playoffName) ?? null
        : playoffComps[0] ?? null;
      setPlayoff(existing);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando playoff");
    } finally {
      setLoading(false);
    }
  }, [seasonId, selectedFormat, defaultFormatId, playoffName]);

  useEffect(() => {
    load();
  }, [load]);

  const currentFormat = formats.find((f) => f.format_id === selectedFormat);

  // Keep the KO CSV input in sync with the regular start + format.
  // Only seeds the default value — the operator can still override.
  useEffect(() => {
    if (!currentFormat) return;
    const start = Number(regularStart);
    if (!Number.isFinite(start) || start < 1) return;
    const koStart = start + currentFormat.n_rounds_regular;
    const numbers = Array.from(
      { length: currentFormat.n_rounds_ko },
      (_, i) => koStart + i,
    );
    setKoMatchdays(numbers.join(","));
  }, [regularStart, currentFormat]);

  async function handleCreate() {
    if (!selectedFormat) return;
    setBusy("create");
    setError(null);
    try {
      const comp = await apiClient.post<CompetitionDetail>(
        `/competitions/admin/season/${seasonId}`,
        playoffName
          ? { format_id: selectedFormat, name: playoffName }
          : { format_id: selectedFormat },
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
    if (!playoff || !currentFormat) return;
    const start = Number(regularStart);
    if (!Number.isFinite(start) || start < 1) {
      setError("Indica una jornada de inicio válida");
      return;
    }
    const end = start + currentFormat.n_rounds_regular - 1;
    // Parse the KO matchday CSV (pre-filled to start+N..start+N+M-1).
    // Sent along with the regular start so the backend can auto-fire
    // the KO phase the moment the last regular cruce resolves —
    // operator does not need to come back to this card.
    const koNumbers = koMatchdays
      .split(",")
      .map((s) => Number(s.trim()))
      .filter((n) => Number.isFinite(n) && n >= 1);
    if (koNumbers.length !== currentFormat.n_rounds_ko) {
      setError(
        `Las jornadas KO deben ser exactamente ${currentFormat.n_rounds_ko} (separadas por coma)`,
      );
      return;
    }
    setBusy("regular");
    setError(null);
    try {
      await apiClient.post(`/competitions/admin/${playoff.id}/start-regular`, {
        matchday_start: start,
        matchday_end: end,
        planned_ko_matchday_numbers: koNumbers,
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
        <h3 className="text-sm font-semibold text-vpv-text">{title}</h3>
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
            Define la jornada inicio y las jornadas KO. El KO arrancará
            automáticamente cuando se resuelva la última jornada de la fase
            regular — no tendrás que volver aquí.
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
              Jornadas KO
              <input
                type="text"
                value={koMatchdays}
                onChange={(e) => setKoMatchdays(e.target.value)}
                placeholder={
                  currentFormat
                    ? Array.from(
                        { length: currentFormat.n_rounds_ko },
                        (_, i) => `${i + 1}`,
                      ).join(",")
                    : ""
                }
                className="ml-2 w-28 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
              />
            </label>
            <button
              onClick={handleStartRegular}
              disabled={busy === "regular"}
              className="rounded bg-vpv-accent px-3 py-1 text-xs font-medium text-vpv-bg transition-opacity disabled:opacity-40"
            >
              {busy === "regular" ? "Generando…" : "Generar calendario"}
            </button>
          </div>
          {currentFormat && Number.isFinite(Number(regularStart)) && Number(regularStart) >= 1 && (
            <p className="text-[11px] text-vpv-text-muted/70">
              Fase regular: J{Number(regularStart)} – J
              {Number(regularStart) + currentFormat.n_rounds_regular - 1}.
              KO: J{koMatchdays || "?"}.
            </p>
          )}
        </div>
      )}

      {playoff && status === "regular" && (
        <div className="space-y-2">
          <p className="text-xs text-vpv-text-muted">
            Fase regular en curso. Si configuraste las jornadas KO al crear el
            calendario, las eliminatorias se iniciarán solas cuando se resuelva
            el último cruce. Si no, fuérzalo desde aquí:
          </p>
          <details className="text-xs">
            <summary className="cursor-pointer text-vpv-text-muted">
              Iniciar KO manualmente (fallback)
            </summary>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <label>
                Jornadas KO
                <input
                  type="text"
                  placeholder="ej: 7,8"
                  value={koMatchdays}
                  onChange={(e) => setKoMatchdays(e.target.value)}
                  className="ml-2 w-28 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-vpv-text"
                />
              </label>
              <button
                onClick={handleStartKo}
                disabled={busy === "ko"}
                className="rounded bg-vpv-accent px-3 py-1 font-medium text-vpv-bg transition-opacity disabled:opacity-40"
              >
                {busy === "ko" ? "Iniciando…" : "Iniciar eliminatorias"}
              </button>
            </div>
          </details>
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
