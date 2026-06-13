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
  MarcaRatingValue,
  MarcaRosterResponse,
  SeasonSummary,
} from "@/types";

const MARCA_OPTIONS: { value: MarcaRatingValue; label: string }[] = [
  { value: "SC", label: "SC (sin calificar)" },
  { value: "★", label: "★" },
  { value: "★★", label: "★★" },
  { value: "★★★", label: "★★★" },
  { value: "★★★★", label: "★★★★" },
  { value: "-", label: "− (no jugó)" },
];

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
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

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
      })
      .catch(() => setMatchdayDetail(null));
  }, [selectedSeason, selectedMatchdayNumber]);

  // Load roster + current marca_rating when a match is picked.
  const fetchRoster = useCallback(async (matchId: number) => {
    setLoading(true);
    setMessage(null);
    try {
      const r = await apiClient.get<MarcaRosterResponse>(
        `/scraping/admin/marca/match/${matchId}/roster`,
      );
      setRoster(r);
      // Seed the dropdowns with whatever marca_rating is already in BD
      // (or "SC" as a sane default for empty rows so submitting is safe).
      const seed: Record<number, MarcaRatingValue> = {};
      const allRows = [...r.home, ...r.away];
      for (const row of allRows) {
        const current = (row.marca_rating ?? "SC") as MarcaRatingValue;
        seed[row.player_id] = current;
      }
      setEdits(seed);
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
    if (selectedMatchId !== null) {
      fetchRoster(selectedMatchId);
    }
  }, [selectedMatchId, fetchRoster]);

  // List of (player_id, new_marca) only when the dropdown differs from
  // the BD value — keeps the body small and avoids re-aggregations
  // that didn't change anything.
  const dirtyAssignments = useMemo<MarcaAssignment[]>(() => {
    if (!roster) return [];
    const allRows = [...roster.home, ...roster.away];
    const out: MarcaAssignment[] = [];
    for (const row of allRows) {
      const next = edits[row.player_id];
      if (!next) continue;
      const current = row.marca_rating ?? "SC";
      if (next !== current) {
        out.push({ player_id: row.player_id, marca_rating: next });
      }
    }
    return out;
  }, [roster, edits]);

  const handleApply = useCallback(async () => {
    if (!roster || dirtyAssignments.length === 0) return;
    setSaving(true);
    setMessage(null);
    try {
      const body: MarcaApplyRequest = {
        match_id: roster.match_id,
        assignments: dirtyAssignments,
      };
      const result = await apiClient.post<{ updated: number }>(
        "/scraping/admin/marca/apply",
        body,
      );
      setMessage(
        `Actualizados ${result.updated} jugadores. Recálculo de jornada disparado.`,
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
  }, [roster, dirtyAssignments, fetchRoster]);

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
              onChange={(playerId, value) =>
                setEdits((prev) => ({ ...prev, [playerId]: value }))
              }
            />
            <TeamColumn
              title={`Visitante — ${teamLabel(roster.away)}`}
              rows={roster.away}
              edits={edits}
              onChange={(playerId, value) =>
                setEdits((prev) => ({ ...prev, [playerId]: value }))
              }
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-vpv-card-border bg-vpv-card p-3">
            <p className="text-xs text-vpv-text-muted">
              {dirtyAssignments.length === 0
                ? "Sin cambios pendientes."
                : `${dirtyAssignments.length} cambio(s) listo(s) para aplicar.`}
            </p>
            <button
              onClick={handleApply}
              disabled={saving || dirtyAssignments.length === 0}
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
  onChange,
}: {
  title: string;
  rows: MarcaPlayerRow[];
  edits: Record<number, MarcaRatingValue>;
  onChange: (playerId: number, value: MarcaRatingValue) => void;
}) {
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-card-border bg-vpv-bg/40 px-3 py-1.5">
        <p className="text-xs font-bold text-vpv-text">{title}</p>
      </div>
      <ul className="divide-y divide-vpv-card-border/40">
        {rows.map((row) => {
          const current = edits[row.player_id] ?? "SC";
          const stale = row.marca_rating ?? "SC";
          const dirty = current !== stale;
          // Players who didn't play get a softer style — the admin's
          // natural default for them is "-" but we don't force it.
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
                {row.minutes_played}'
              </span>
              <select
                value={current}
                onChange={(e) =>
                  onChange(row.player_id, e.target.value as MarcaRatingValue)
                }
                className={`rounded border bg-vpv-bg px-1.5 py-0.5 text-xs text-vpv-text ${
                  dirty ? "border-vpv-accent" : "border-vpv-border"
                }`}
              >
                {MARCA_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
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
