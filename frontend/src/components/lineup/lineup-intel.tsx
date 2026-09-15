"use client";

import { useEffect, useRef, useState } from "react";

import { apiClient, ApiClientError } from "@/lib/api-client";
import type { SquadPlayerEntry } from "@/types";

// What futbolfantasy, analiticafantasy and predicted11's best predictors say
// about each player this matchday, and the eleven the optimizer proposes.
// Admin only, like the predictions.

export interface SourceReading {
  source: string;
  probability: number | null;
  previous_probability: number | null;
  starter: boolean;
  status: string | null;
  note: string | null;
  fetched_at: string;
}

/** A predicted11 predictor with an eleven for a team: whoever of that team
 * is missing from it counts 0 for him. */
export interface SourceCoverage {
  source: string;
  team_id: number;
  team_name: string;
  note: string | null;
}

export interface LineupIntelResponse {
  season_id: number;
  matchday_number: number;
  updated_at: string | null;
  players: { player_id: number; readings: SourceReading[] }[];
  coverage?: SourceCoverage[];
}

interface RefreshStarted {
  started: boolean;
  message: string;
}

// With predicted11 a refresh takes minutes: it runs in the background and the
// screen reads the sources again until their time changes.
export const REFRESH_POLL_MS = 15_000;
export const REFRESH_MAX_WAIT_MS = 8 * 60_000;

export interface SuggestedPlayer {
  player_id: number;
  name: string;
  position: string;
  team_name: string;
  value: number;
  xpts_if_plays: number | null;
  play_prob: number;
  basis: string;
}

export interface SuggestionResponse {
  season_id: number;
  matchday_number: number;
  formation: string;
  total: number;
  eleven: SuggestedPlayer[];
  bench: SuggestedPlayer[];
}

const SOURCE_LABEL: Record<string, string> = {
  futbolfantasy: "FF",
  analiticafantasy: "AF",
};

// predicted11_1 … _3: one source per predictor, shown together as "P11 2/3".
const isP11 = (source: string) => source.startsWith("predicted11_");

// Gravest first, as the backend ranks them.
const STATUS_ORDER = [
  "sancionado",
  "no_disponible",
  "lesionado",
  "duda",
  "rotacion",
  "apercibido",
] as const;

const STATUS_LABEL: Record<string, string> = {
  sancionado: "Sancionado",
  no_disponible: "No disponible",
  lesionado: "Lesionado",
  duda: "Duda",
  rotacion: "Rotación",
  apercibido: "Apercibido",
};

const STATUS_STYLE: Record<string, string> = {
  sancionado: "bg-red-500/15 text-red-400",
  no_disponible: "bg-red-500/15 text-red-400",
  lesionado: "bg-red-500/15 text-red-400",
  duda: "bg-amber-500/15 text-amber-400",
  rotacion: "bg-sky-500/15 text-sky-400",
  apercibido: "bg-yellow-500/15 text-yellow-400",
};

export function formatReadAt(iso: string): string {
  const d = new Date(iso);
  const day = d.toLocaleDateString("es-ES", { weekday: "short", day: "numeric" });
  const time = d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  return `${day} ${time}`;
}

export function readingsByPlayer(
  intel: LineupIntelResponse | null | undefined,
): Map<number, SourceReading[]> {
  return new Map((intel?.players ?? []).map((p) => [p.player_id, p.readings]));
}

/** The predicted11 predictors with an eleven for each team, by team name. */
export function coverageByTeam(
  intel: LineupIntelResponse | null | undefined,
): Map<string, SourceCoverage[]> {
  const out = new Map<string, SourceCoverage[]>();
  for (const item of intel?.coverage ?? []) {
    out.set(item.team_name, [...(out.get(item.team_name) ?? []), item]);
  }
  return out;
}

/** The squad entries of the proposed eleven, in its order. */
export function applySuggestion(
  squad: SquadPlayerEntry[],
  suggestion: SuggestionResponse,
): SquadPlayerEntry[] {
  const byId = new Map(squad.map((p) => [p.player_id, p]));
  return suggestion.eleven
    .map((p) => byId.get(p.player_id))
    .filter((p): p is SquadPlayerEntry => p !== undefined);
}

/** "FF 70% ↑ · AF 60% · P11 2/3 · Duda" under a player card. */
export function SourceBadges({
  readings = [],
  coverage = [],
}: {
  readings?: SourceReading[];
  coverage?: SourceCoverage[];
}) {
  const plain = readings.filter((r) => !isP11(r.source));
  const picked = new Set(readings.filter((r) => isP11(r.source)).map((r) => r.source));
  // Who has an eleven for his team, plus anyone who picks him: the rest leave him out.
  const predictors = new Map(coverage.map((c) => [c.source, c.note ?? c.source]));
  for (const r of readings) {
    if (isP11(r.source) && !predictors.has(r.source)) predictors.set(r.source, r.note ?? r.source);
  }
  if (plain.length === 0 && predictors.size === 0) return null;
  const gravest = STATUS_ORDER.find((s) => plain.some((r) => r.status === s));
  const notes = plain
    .filter((r) => r.note)
    .map((r) => `${SOURCE_LABEL[r.source] ?? r.source}: ${r.note}`)
    .join("\n");

  return (
    <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px]">
      {plain.map((r) => {
        const label = SOURCE_LABEL[r.source] ?? r.source;
        const changed =
          r.probability !== null &&
          r.previous_probability !== null &&
          r.probability !== r.previous_probability;
        return (
          <span
            key={r.source}
            className="tabular-nums text-vpv-text-muted"
            title={`${r.source}: ${r.starter ? "titular" : "suplente"} en su once probable · leído ${formatReadAt(r.fetched_at)}`}
          >
            <span className="font-semibold text-vpv-text">{label}</span>{" "}
            {r.probability === null ? "–" : `${r.probability}%`}
            {changed && (
              <span
                className={
                  r.probability! > r.previous_probability!
                    ? "ml-0.5 text-emerald-400"
                    : "ml-0.5 text-red-400"
                }
                title={`antes ${r.previous_probability}%`}
              >
                {r.probability! > r.previous_probability! ? "↑" : "↓"}
              </span>
            )}
          </span>
        );
      })}
      {predictors.size > 0 && (
        <span
          className="tabular-nums text-vpv-text-muted"
          title={[...predictors.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([source, who]) => `${picked.has(source) ? "✓" : "✗"} ${who}`)
            .join("\n")}
        >
          <span className="font-semibold text-vpv-text">P11</span> {picked.size}/{predictors.size}
        </span>
      )}
      {gravest && (
        <span
          className={`rounded px-1 py-px font-medium ${STATUS_STYLE[gravest]}`}
          title={notes || STATUS_LABEL[gravest]}
        >
          {STATUS_LABEL[gravest]}
        </span>
      )}
    </div>
  );
}

/** When the sources were read, and the two admin actions of the screen. */
export function LineupAdminBar({
  seasonId,
  matchday,
  updatedAt,
  onRefreshed,
  onSuggestion,
}: {
  seasonId: number;
  matchday: number;
  updatedAt: string | null;
  onRefreshed: () => void;
  onSuggestion: (suggestion: SuggestionResponse) => void;
}) {
  const [busy, setBusy] = useState<"refresh" | "propose" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  // A refresh running in the background: the time the sources had when it
  // started, and when it started.
  const [pending, setPending] = useState<{ from: string | null; at: number } | null>(null);
  const waiting = pending !== null && pending.from === updatedAt;
  const reread = useRef(onRefreshed);
  useEffect(() => {
    reread.current = onRefreshed;
  });

  useEffect(() => {
    if (!waiting || pending === null) return;
    const id = setInterval(() => {
      if (Date.now() - pending.at > REFRESH_MAX_WAIT_MS) {
        setPending(null);
        setMessage("La actualización no ha terminado: vuelve a mirar dentro de un rato.");
        return;
      }
      reread.current();
    }, REFRESH_POLL_MS);
    return () => clearInterval(id);
  }, [waiting, pending]);

  async function refresh() {
    setBusy("refresh");
    setMessage(null);
    try {
      await apiClient.post<RefreshStarted>(`/lineup-intel/${seasonId}/${matchday}/refresh`, {});
      setPending({ from: updatedAt, at: Date.now() });
    } catch (err) {
      setMessage(
        err instanceof ApiClientError ? err.error.message : "No se ha podido actualizar.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function propose() {
    setBusy("propose");
    setMessage(null);
    try {
      onSuggestion(
        await apiClient.get<SuggestionResponse>(
          `/lineup-assistant/${seasonId}/${matchday}/suggestion`,
        ),
      );
    } catch (err) {
      setMessage(
        err instanceof ApiClientError ? err.error.message : "No se ha podido proponer un once.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-vpv-card-border bg-vpv-card px-3 py-2 text-xs">
      <span className="text-vpv-text-muted">
        Alineaciones probables:{" "}
        {updatedAt ? `leídas el ${formatReadAt(updatedAt)}` : "sin datos todavía"}
      </span>
      <div className="ml-auto flex gap-2">
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={busy !== null || waiting}
          className="rounded-md border border-vpv-card-border px-3 py-1 text-vpv-text hover:border-vpv-border disabled:opacity-40"
        >
          {waiting
            ? "Actualizando… (unos minutos)"
            : busy === "refresh"
              ? "Actualizando…"
              : "Actualizar"}
        </button>
        <button
          type="button"
          onClick={() => void propose()}
          disabled={busy !== null}
          className="rounded-md bg-vpv-accent px-3 py-1 font-medium text-white hover:bg-vpv-accent-hover disabled:opacity-40"
        >
          {busy === "propose" ? "Calculando…" : "Proponer once"}
        </button>
      </div>
      {message && (
        <p role="status" className="w-full text-vpv-danger">
          {message}
        </p>
      )}
    </div>
  );
}

/** Why each player of the proposed eleven is there. */
export function SuggestionPanel({
  suggestion,
  onClose,
}: {
  suggestion: SuggestionResponse;
  onClose: () => void;
}) {
  return (
    <div className="rounded-lg border border-vpv-accent/30 bg-vpv-accent/5 px-3 py-2 text-xs">
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-semibold text-vpv-text">
          Once propuesto {suggestion.formation} ·{" "}
          <span className="tabular-nums">{suggestion.total.toFixed(1)}</span> puntos esperados
        </p>
        <button
          type="button"
          onClick={onClose}
          className="text-vpv-text-muted hover:text-vpv-text"
        >
          Cerrar
        </button>
      </div>
      <p className="text-vpv-text-muted">
        Ya está en el campo, sin enviar: cambia lo que quieras y envíala tú.
      </p>
      <ul className="mt-1.5 space-y-0.5">
        {suggestion.eleven.map((p) => (
          <li key={p.player_id} className="tabular-nums">
            <span className="text-vpv-text-muted">{p.position}</span>{" "}
            <span className="font-medium text-vpv-text">{p.name}</span> ·{" "}
            {/* Without a forecast the basis says why: no match, or no data yet. */}
            {p.xpts_if_plays === null
              ? "0 puntos"
              : `${p.value.toFixed(1)} = ${p.xpts_if_plays.toFixed(1)} si juega × ${Math.round(p.play_prob * 100)}%`}{" "}
            · <span className="text-vpv-text-muted">{p.basis}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
