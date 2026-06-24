"use client";

/**
 * Notas Marca — admin tool.
 *
 * Two tabs over the same backing endpoint:
 *   1. "Entrada manual": render a dropdown per player and write the
 *      ratings directly.
 *   2. "Subir imagen": OCR the press clipping and pre-fill the same
 *      dropdowns (added in a follow-up).
 *
 * Gated by Perm.MARCA via /admin/layout.tsx so the role can be
 * delegated to someone who doesn't have SCRAPING/STATS.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { apiClient } from "@/lib/api-client";
import type {
  MarcaApplyRequest,
  MarcaAssignment,
  MarcaPlayerRow,
  MarcaPreviewResponse,
  MarcaRatingValue,
  MarcaRosterResponse,
  PicasApplyRequest,
  PicasAssignment,
  PicasValue,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

type ModeTab = "manual" | "image";

// Sentinel para que <option value=""> represente "no jugó" (null en BD).
const NO_PLAYED_SENTINEL = "";

// `value` is what the BD / API store. `label` is what the user sees
// in the dropdown — the star levels render as ★/★★/… for clarity.
const MARCA_OPTIONS: { sentinel: string; value: MarcaRatingValue; label: string }[] = [
  { sentinel: NO_PLAYED_SENTINEL, value: null, label: "no jugó" },
  { sentinel: "SC", value: "SC", label: "SC (jugó poco, no valorable)" },
  { sentinel: "-", value: "-", label: "− (jugó mal)" },
  { sentinel: "1", value: "1", label: "★" },
  { sentinel: "2", value: "2", label: "★★" },
  { sentinel: "3", value: "3", label: "★★★" },
  { sentinel: "4", value: "4", label: "★★★★" },
];

function sentinelFor(rating: MarcaRatingValue): string {
  return rating === null ? NO_PLAYED_SENTINEL : rating;
}

function ratingFromSentinel(s: string): MarcaRatingValue {
  if (s === NO_PLAYED_SENTINEL) return null;
  return s as MarcaRatingValue;
}

// Picas as visual glyphs (bullets), mirroring the star style of the
// marca dropdown so the row reads "★★ ●●" at a glance instead of
// "2 estrellas / 2 picas".
const PICAS_OPTIONS: { sentinel: string; value: PicasValue; label: string }[] = [
  { sentinel: NO_PLAYED_SENTINEL, value: null, label: "no jugó" },
  { sentinel: "SC", value: "SC", label: "SC (sin calificar)" },
  { sentinel: "-", value: "-", label: "− (jugó mal)" },
  { sentinel: "0", value: "0", label: "○ (jugó, sin picas)" },
  { sentinel: "1", value: "1", label: "●" },
  { sentinel: "2", value: "2", label: "●●" },
  { sentinel: "3", value: "3", label: "●●●" },
];

function picasSentinelFor(v: PicasValue | string | null | undefined): string {
  if (v === null || v === undefined) return NO_PLAYED_SENTINEL;
  return v;
}

function picasFromSentinel(s: string): PicasValue {
  if (s === NO_PLAYED_SENTINEL) return null;
  return s as PicasValue;
}

interface MatchdaySummary {
  number: number;
  status: string;
  counts: boolean;
  stats_ok: boolean;
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
  matches: MatchEntry[];
}

export default function AdminMarcaPage() {
  const { selectedSeason } = useSeason();
  const [matchdays, setMatchdays] = useState<MatchdaySummary[]>([]);
  const [selectedMatchdayNumber, setSelectedMatchdayNumber] = useState<number | null>(null);
  const [matchdayDetail, setMatchdayDetail] = useState<MatchdayDetail | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null);
  const [roster, setRoster] = useState<MarcaRosterResponse | null>(null);
  const [edits, setEdits] = useState<Record<number, MarcaRatingValue>>({});
  const [picasEdits, setPicasEdits] = useState<Record<number, PicasValue>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [mode, setMode] = useState<ModeTab>("manual");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [preview, setPreview] = useState<MarcaPreviewResponse | null>(null);
  // Bumped to remount the <input type="file">, sidestepping the
  // browser behavior of NOT firing onChange when the same file is
  // re-selected. Also bumped on match change so the previous file
  // doesn't linger.
  const [fileInputKey, setFileInputKey] = useState(0);

  // Drop any in-memory image / OCR state. Called when the file is
  // cleared, when the match changes, or after a fresh upload starts.
  const clearImageState = useCallback(() => {
    setImageFile(null);
    setImagePreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setPreview(null);
    setUploadBusy(false);
    setFileInputKey((k) => k + 1);
  }, []);

  // Fetch matchdays when the season changes.
  useEffect(() => {
    if (!selectedSeason) return;
    apiClient
      .get<{ matchdays: MatchdaySummary[] }>(
        `/matchdays/${selectedSeason.id}?stats_ok_only=false`,
      )
      .then((d) => {
        setMatchdays(d.matchdays.filter((m) => m.counts));
        setSelectedMatchdayNumber(null);
        setMatchdayDetail(null);
        setSelectedMatchId(null);
        setRoster(null);
        setEdits({});
      })
      .catch(() => setMatchdays([]));
  }, [selectedSeason]);

  // Fetch matchday detail to populate the match picker.
  useEffect(() => {
    if (!selectedSeason || selectedMatchdayNumber === null) {
      setMatchdayDetail(null);
      return;
    }
    apiClient
      .get<MatchdayDetail>(
        `/matchdays/${selectedSeason.id}/${selectedMatchdayNumber}`,
      )
      .then((d) => {
        setMatchdayDetail(d);
        setSelectedMatchId(null);
        setRoster(null);
        setEdits({});
        setPicasEdits({});
        clearImageState();
        setMessage(null);
      })
      .catch(() => setMatchdayDetail(null));
  }, [selectedSeason, selectedMatchdayNumber, clearImageState]);

  // Load roster + current marca_rating when a match is picked.
  const fetchRoster = useCallback(async (matchId: number) => {
    setLoading(true);
    setMessage(null);
    try {
      const r = await apiClient.get<MarcaRosterResponse>(
        `/scraping/admin/marca/match/${matchId}/roster`,
      );
      setRoster(r);
      // Seed the dropdowns with whatever marca_rating is already in BD.
      // null en BD ⇒ "no jugó" en el dropdown (sentinel "").
      const seed: Record<number, MarcaRatingValue> = {};
      const seedPicas: Record<number, PicasValue> = {};
      const allRows = [...r.home, ...r.away];
      for (const row of allRows) {
        seed[row.player_id] = (row.marca_rating ?? null) as MarcaRatingValue;
        seedPicas[row.player_id] = (row.as_picas ?? null) as PicasValue;
      }
      setEdits(seed);
      setPicasEdits(seedPicas);
    } catch (err) {
      setMessage(
        `Error cargando roster: ${err instanceof Error ? err.message : "desconocido"}`,
      );
      setRoster(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Always drop the previous match's image/preview when the picked
    // match changes — otherwise the OCR result from match A sticks
    // around while the admin is reviewing match B.
    clearImageState();
    setMessage(null);
    if (selectedMatchId !== null) {
      fetchRoster(selectedMatchId);
    } else {
      setRoster(null);
      setEdits({});
      setPicasEdits({});
    }
  }, [selectedMatchId, fetchRoster, clearImageState]);

  // List of (player_id, new_marca) only when the dropdown differs from
  // the BD value — keeps the body small and avoids re-aggregations
  // that didn't change anything.
  const dirtyAssignments = useMemo<MarcaAssignment[]>(() => {
    if (!roster) return [];
    const allRows = [...roster.home, ...roster.away];
    const out: MarcaAssignment[] = [];
    for (const row of allRows) {
      // edits puede contener null intencionalmente ("no jugó"), así
      // que sólo descartamos cuando la entrada no existe en el dict.
      if (!(row.player_id in edits)) continue;
      const next = edits[row.player_id];
      const current = (row.marca_rating ?? null) as MarcaRatingValue;
      if (next !== current) {
        out.push({ player_id: row.player_id, marca_rating: next });
      }
    }
    return out;
  }, [roster, edits]);

  const dirtyPicasAssignments = useMemo<PicasAssignment[]>(() => {
    if (!roster) return [];
    const allRows = [...roster.home, ...roster.away];
    const out: PicasAssignment[] = [];
    for (const row of allRows) {
      if (!(row.player_id in picasEdits)) continue;
      const next = picasEdits[row.player_id];
      const current = (row.as_picas ?? null) as PicasValue;
      if (next !== current) {
        out.push({ player_id: row.player_id, as_picas: next });
      }
    }
    return out;
  }, [roster, picasEdits]);

  const handleUpload = useCallback(async () => {
    if (!selectedMatchId || !imageFile) return;
    setUploadBusy(true);
    setMessage(null);
    try {
      const form = new FormData();
      form.append("match_id", String(selectedMatchId));
      form.append("image", imageFile);
      const token =
        typeof window !== "undefined" ? window.localStorage.getItem("vpv_token") : null;
      const res = await fetch(`${API_BASE_URL}/scraping/admin/marca/preview`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: form,
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = (await res.json()) as MarcaPreviewResponse;
      setPreview(data);
      // Auto-apply each successful match into the dropdown state so the
      // admin can review the whole roster and tweak before "Aplicar".
      // marca_rating can be null when the parser found neither stars
      // nor a textual marker — leave the dropdown at "no jugó".
      setEdits((prev) => {
        const next = { ...prev };
        for (const m of data.matches) {
          next[m.player_id] = (m.marca_rating ?? null) as MarcaRatingValue;
        }
        return next;
      });
      setMessage(
        `OCR: ${data.matches.length} jugador(es) identificado(s) automáticamente,` +
          ` ${data.unmatched.length} pendiente(s).`,
      );
      // Remount the file input so the admin can re-pick the SAME
      // image (e.g. after a manual tweak) without having to click
      // "Quitar imagen" first.
      setFileInputKey((k) => k + 1);
    } catch (err) {
      setMessage(
        `Error subiendo: ${err instanceof Error ? err.message : "desconocido"}`,
      );
    } finally {
      setUploadBusy(false);
    }
  }, [selectedMatchId, imageFile]);

  const handleApply = useCallback(async () => {
    if (!roster) return;
    if (dirtyAssignments.length === 0 && dirtyPicasAssignments.length === 0) return;
    setSaving(true);
    setMessage(null);
    try {
      let marcaUpdated = 0;
      let picasUpdated = 0;
      if (dirtyAssignments.length > 0) {
        const body: MarcaApplyRequest = {
          match_id: roster.match_id,
          assignments: dirtyAssignments,
        };
        const result = await apiClient.post<{ updated: number }>(
          "/scraping/admin/marca/apply",
          body,
        );
        marcaUpdated = result.updated;
      }
      if (dirtyPicasAssignments.length > 0) {
        const body: PicasApplyRequest = {
          match_id: roster.match_id,
          assignments: dirtyPicasAssignments,
        };
        const result = await apiClient.post<{ updated: number }>(
          "/scraping/admin/marca/apply-picas",
          body,
        );
        picasUpdated = result.updated;
      }
      const bits: string[] = [];
      if (marcaUpdated) bits.push(`${marcaUpdated} Marca`);
      if (picasUpdated) bits.push(`${picasUpdated} Picas`);
      setMessage(
        `Actualizados ${bits.join(" + ")}. Recálculo de jornada disparado.`,
      );
      // Re-fetch to reflect the new "current" values.
      await fetchRoster(roster.match_id);
    } catch (err) {
      setMessage(
        `Error aplicando: ${err instanceof Error ? err.message : "desconocido"}`,
      );
    } finally {
      setSaving(false);
    }
  }, [roster, dirtyAssignments, dirtyPicasAssignments, fetchRoster]);

  if (!selectedSeason) {
    return (
      <p className="py-6 text-center text-sm text-vpv-text-muted">
        Selecciona una temporada en el header.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-vpv-text">Notas Marca</h1>
        <p className="text-xs text-vpv-text-muted">
          {selectedSeason.name} — escribe las puntuaciones a mano por
          partido y se recalculan los puntos de la jornada automáticamente.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-vpv-text-muted">Jornada</label>
        <select
          value={selectedMatchdayNumber ?? ""}
          onChange={(e) =>
            setSelectedMatchdayNumber(e.target.value ? Number(e.target.value) : null)
          }
          className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
        >
          <option value="">— elige jornada —</option>
          {matchdays.map((m) => (
            <option key={m.number} value={m.number}>
              J{m.number}
            </option>
          ))}
        </select>

        {matchdayDetail && matchdayDetail.matches.length > 0 && (
          <>
            <label className="text-xs text-vpv-text-muted">Partido</label>
            <select
              value={selectedMatchId ?? ""}
              onChange={(e) =>
                setSelectedMatchId(e.target.value ? Number(e.target.value) : null)
              }
              className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
            >
              <option value="">— elige partido —</option>
              {matchdayDetail.matches
                .filter((m) => m.counts)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.home_team} {m.home_score ?? "-"}-{m.away_score ?? "-"}{" "}
                    {m.away_team}
                  </option>
                ))}
            </select>
          </>
        )}
      </div>

      {selectedMatchId !== null && (
        <div className="flex gap-1 border-b border-vpv-border pb-px text-xs">
          {(["manual", "image"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-t-md px-3 py-1.5 font-medium transition-colors ${
                mode === m
                  ? "border-b-2 border-vpv-accent text-vpv-accent"
                  : "text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {m === "manual" ? "Entrada manual" : "Subir imagen (OCR)"}
            </button>
          ))}
        </div>
      )}

      {mode === "image" && selectedMatchId !== null && (
        <div className="space-y-3 rounded-lg border border-vpv-card-border bg-vpv-card p-3 text-xs">
          <p className="text-vpv-text-muted">
            Sube el cromo de Marca del partido. El servidor lee los nombres y
            cuenta las estrellas (rojas), y rellena los desplegables de la
            pestaña Manual con la propuesta. Después puedes corregir los que
            haga falta y pulsar &quot;Aplicar&quot;.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {/* Hidden native input + styled <label> that triggers it.
                The label gets the same key bump as before so picking
                the same file twice still works. */}
            <input
              id={`marca-file-${fileInputKey}`}
              key={fileInputKey}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null;
                setImageFile(file);
                setImagePreviewUrl((prev) => {
                  if (prev) URL.revokeObjectURL(prev);
                  return file ? URL.createObjectURL(file) : null;
                });
                setPreview(null);
                setMessage(null);
              }}
              className="sr-only"
            />
            <label
              htmlFor={`marca-file-${fileInputKey}`}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-vpv-border bg-vpv-bg px-3 py-1.5 text-xs font-medium text-vpv-text transition-colors hover:bg-vpv-card hover:border-vpv-accent/50"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="h-3.5 w-3.5"
              >
                <path
                  fillRule="evenodd"
                  d="M10 3a.75.75 0 01.75.75v6.5l1.95-1.95a.75.75 0 111.06 1.06l-3.23 3.22a.75.75 0 01-1.06 0L6.24 9.36a.75.75 0 011.06-1.06l1.95 1.95V3.75A.75.75 0 0110 3zM4.75 14a.75.75 0 01.75.75v.75c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-.75a.75.75 0 011.5 0v.75A2.25 2.25 0 0114.75 17h-8.5A2.25 2.25 0 014 14.75v-.75A.75.75 0 014.75 14z"
                  clipRule="evenodd"
                />
              </svg>
              {imageFile ? "Cambiar imagen" : "Seleccionar imagen"}
            </label>

            {imageFile && (
              <span
                className="max-w-[220px] truncate text-xs text-vpv-text-muted"
                title={imageFile.name}
              >
                {imageFile.name}
              </span>
            )}

            <button
              onClick={handleUpload}
              disabled={uploadBusy || !imageFile}
              className="ml-auto rounded-md bg-vpv-accent px-3 py-1.5 text-xs font-bold text-white shadow-sm transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            >
              {uploadBusy ? "Procesando…" : "Procesar imagen"}
            </button>
            {(imageFile || preview) && (
              <button
                onClick={clearImageState}
                disabled={uploadBusy}
                className="rounded-md border border-vpv-border bg-vpv-bg px-3 py-1.5 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-40"
                title="Descartar imagen y propuesta OCR"
              >
                Quitar
              </button>
            )}
          </div>

          {imagePreviewUrl && (
            // Pequeña vista previa, no decisiva — solo confirma que es el cromo
            // correcto.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imagePreviewUrl}
              alt="Vista previa del cromo"
              className="max-h-64 rounded border border-vpv-border"
            />
          )}

          {preview && preview.unmatched.length > 0 && (
            <div className="space-y-1">
              <p className="font-medium text-amber-300">
                Pendientes de asignar ({preview.unmatched.length})
              </p>
              <ul className="space-y-1">
                {preview.unmatched.map((u, idx) => (
                  <li
                    key={`${u.row.surname_clean}-${idx}`}
                    className="flex flex-wrap items-center gap-2 rounded bg-vpv-bg/40 p-2 text-vpv-text"
                  >
                    <span className="font-mono text-[10px] text-vpv-text-muted">
                      {u.row.raw_text}
                    </span>
                    <span className="rounded bg-vpv-accent/20 px-1.5 py-0.5 text-[10px] text-vpv-accent">
                      {u.row.stars > 0
                        ? "★".repeat(u.row.stars)
                        : u.row.explicit_marker === "dash"
                          ? "−"
                          : u.row.explicit_marker === "sc"
                            ? "SC"
                            : "—"}
                    </span>
                    <select
                      defaultValue=""
                      onChange={(e) => {
                        const pid = Number(e.target.value);
                        if (!Number.isFinite(pid) || pid === 0) return;
                        const newRating: MarcaRatingValue =
                          u.row.stars > 0
                            ? (String(u.row.stars) as MarcaRatingValue)
                            : u.row.explicit_marker === "dash"
                              ? ("-" as MarcaRatingValue)
                              : u.row.explicit_marker === "sc"
                                ? ("SC" as MarcaRatingValue)
                                : null;
                        setEdits((prev) => ({ ...prev, [pid]: newRating }));
                      }}
                      className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
                    >
                      <option value="">— asignar a jugador —</option>
                      {u.candidates.map((c) => (
                        <option key={c.player_id} value={c.player_id}>
                          {c.display_name} ({c.team_name})
                        </option>
                      ))}
                    </select>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {message && (
        <p
          className={`rounded-lg border p-3 text-xs ${
            message.startsWith("Error")
              ? "border-red-500/30 bg-red-500/10 text-red-300"
              : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
          }`}
        >
          {message}
        </p>
      )}

      {loading && (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded-lg bg-vpv-border" />
          ))}
        </div>
      )}

      {!loading && roster && (
        <>
          <div className="grid gap-3 lg:grid-cols-2">
            <TeamColumn
              title={`Local — ${teamLabel(roster.home)}`}
              rows={roster.home}
              edits={edits}
              picasEdits={picasEdits}
              onChange={(playerId, value) =>
                setEdits((prev) => ({ ...prev, [playerId]: value }))
              }
              onChangePicas={(playerId, value) =>
                setPicasEdits((prev) => ({ ...prev, [playerId]: value }))
              }
            />
            <TeamColumn
              title={`Visitante — ${teamLabel(roster.away)}`}
              rows={roster.away}
              edits={edits}
              picasEdits={picasEdits}
              onChange={(playerId, value) =>
                setEdits((prev) => ({ ...prev, [playerId]: value }))
              }
              onChangePicas={(playerId, value) =>
                setPicasEdits((prev) => ({ ...prev, [playerId]: value }))
              }
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-vpv-card-border bg-vpv-card p-3">
            <p className="text-xs text-vpv-text-muted">
              {dirtyAssignments.length === 0 && dirtyPicasAssignments.length === 0
                ? "Sin cambios pendientes."
                : `${dirtyAssignments.length + dirtyPicasAssignments.length} cambio(s) listo(s) para aplicar` +
                  (dirtyAssignments.length && dirtyPicasAssignments.length
                    ? ` (${dirtyAssignments.length} Marca · ${dirtyPicasAssignments.length} Picas).`
                    : ".")}
            </p>
            <button
              onClick={handleApply}
              disabled={
                saving ||
                (dirtyAssignments.length === 0 && dirtyPicasAssignments.length === 0)
              }
              className="rounded bg-vpv-accent px-4 py-1.5 text-xs font-bold text-white disabled:opacity-40"
            >
              {saving ? "Aplicando…" : "Aplicar"}
            </button>
          </div>
        </>
      )}

      {!loading && roster === null && selectedMatchId !== null && (
        <p className="py-6 text-center text-sm text-vpv-text-muted">
          No se pudo cargar el roster.
        </p>
      )}
    </div>
  );
}

function teamLabel(rows: MarcaPlayerRow[]): string {
  return rows[0]?.team_name ?? "—";
}

function TeamColumn({
  title,
  rows,
  edits,
  picasEdits,
  onChange,
  onChangePicas,
}: {
  title: string;
  rows: MarcaPlayerRow[];
  edits: Record<number, MarcaRatingValue>;
  picasEdits: Record<number, PicasValue>;
  onChange: (playerId: number, value: MarcaRatingValue) => void;
  onChangePicas: (playerId: number, value: PicasValue) => void;
}) {
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-card-border bg-vpv-bg/40 px-3 py-1.5">
        <p className="text-xs font-bold text-vpv-text">{title}</p>
      </div>
      <ul className="divide-y divide-vpv-card-border/40">
        {rows.map((row) => {
          const current = (edits[row.player_id] ?? null) as MarcaRatingValue;
          const stale = (row.marca_rating ?? null) as MarcaRatingValue;
          const dirty = current !== stale;
          const currentPicas = (picasEdits[row.player_id] ?? null) as PicasValue;
          const stalePicas = (row.as_picas ?? null) as PicasValue;
          const dirtyPicas = currentPicas !== stalePicas;
          // Players who didn't play get a softer style — el default
          // natural para ellos es "no jugó" pero no lo forzamos.
          const benched = row.minutes_played === 0;
          return (
            <li
              key={row.player_id}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs ${
                benched ? "opacity-60" : ""
              }`}
            >
              <span className="w-7 text-center text-[10px] font-mono text-vpv-text-muted">
                {row.position || "—"}
              </span>
              <span className="flex-1 truncate text-vpv-text">{row.display_name}</span>
              <span className="w-10 text-right text-[10px] tabular-nums text-vpv-text-muted">
                {row.minutes_played}&apos;
              </span>
              <select
                value={sentinelFor(current)}
                onChange={(e) =>
                  onChange(row.player_id, ratingFromSentinel(e.target.value))
                }
                className={`rounded border bg-vpv-bg px-1.5 py-0.5 text-xs text-vpv-text ${
                  dirty ? "border-vpv-accent" : "border-vpv-border"
                }`}
                title="Marca"
              >
                {MARCA_OPTIONS.map((opt) => (
                  <option key={opt.sentinel} value={opt.sentinel}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <select
                value={picasSentinelFor(currentPicas)}
                onChange={(e) =>
                  onChangePicas(row.player_id, picasFromSentinel(e.target.value))
                }
                className={`rounded border bg-vpv-bg px-1.5 py-0.5 text-xs font-bold ${
                  dirtyPicas
                    ? "border-vpv-accent"
                    : row.as_picas_admin_set
                      ? "border-amber-500/60"
                      : "border-vpv-border"
                } ${
                  currentPicas === "1" || currentPicas === "2" || currentPicas === "3"
                    ? "text-red-500"
                    : "text-vpv-text"
                }`}
                title={
                  row.as_picas_admin_set
                    ? "AS picas (editado manualmente — el scrape ya no lo machaca)"
                    : "AS picas"
                }
              >
                {PICAS_OPTIONS.map((opt) => (
                  <option key={opt.sentinel} value={opt.sentinel}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
