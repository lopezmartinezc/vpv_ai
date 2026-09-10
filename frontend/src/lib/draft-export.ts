/**
 * Export the draft board to a spreadsheet.
 *
 * CSV rather than a real .xlsx on purpose: `xlsx` (SheetJS) on the npm
 * registry has been unpublished since 2022 and carries known advisories, and
 * `exceljs` is about a megabyte for one button. The cost of CSV is locale
 * handling, and that is entirely solvable — a BOM so Excel reads UTF-8 and
 * accents survive, semicolons so Spanish Excel splits the columns without an
 * import wizard, and decimal commas so numbers arrive as numbers you can sort
 * and filter rather than as text.
 *
 * Every column travels, including the model scores the table keeps hidden and
 * the fields it has no room for at all — the point of exporting is to have
 * what the screen cannot show.
 */

import type { DraftValuePlayer } from "@/types";
import { confidenceFor } from "./draft-confidence";
import { PLAYER_TAG_LABELS } from "./player-tags";

const SEPARATOR = ";";
/** Excel only reads a CSV as UTF-8 when it opens with a byte-order mark. */
const BOM = "﻿";

export interface ExportColumn {
  header: string;
  /** A number stays a number; strings are escaped. `null` becomes an empty cell. */
  value: (p: DraftValuePlayer) => string | number | null | undefined;
}

const pct = (v: number | null | undefined): number | null =>
  v === null || v === undefined ? null : Math.round(v * 1000) / 10;

export const EXPORT_COLUMNS: ExportColumn[] = [
  { header: "Ronda est.", value: (p) => p.overall_rank },
  { header: "Jugador", value: (p) => p.display_name },
  { header: "Equipo", value: (p) => p.team_name },
  { header: "Posicion", value: (p) => p.position },
  { header: "Tier", value: (p) => p.position_tier },
  { header: "Fichado", value: (p) => (p.is_drafted ? "si" : "no") },
  // The decision axis, in reading order.
  { header: "Prioridad", value: (p) => p.priority },
  { header: "Prioridad base", value: (p) => p.priority_base },
  { header: "VORP", value: (p) => p.vorp },
  { header: "Salto", value: (p) => p.next_gap },
  { header: "Pts restantes", value: (p) => p.proj_rest_points },
  { header: "Valor efectivo", value: (p) => p.effective_value },
  { header: "Valor manual", value: (p) => p.manual_value },
  // Confidence is computed for the screen; exporting the number without the
  // reason would drop the half that explains it.
  { header: "Confianza", value: (p) => Math.round(confidenceFor(p).score * 100) },
  { header: "Motivo confianza", value: (p) => confidenceFor(p).reason },
  // Playing time.
  { header: "Participacion %", value: (p) => pct(p.participation) },
  { header: "Jornadas restantes est.", value: (p) => p.exp_games_remaining },
  { header: "Disponibilidad %", value: (p) => pct(p.availability) },
  { header: "Partidos jugados", value: (p) => p.games_played },
  { header: "Temporadas", value: (p) => p.seasons_played },
  // Model scores — hidden behind "+ Columnas" on screen, always exported.
  { header: "Ensemble", value: (p) => p.ensemble_score },
  { header: "Media simple", value: (p) => p.simple_avg },
  { header: "Forma 2a mitad", value: (p) => p.second_half_score },
  { header: "Estabilidad", value: (p) => p.stability_score },
  { header: "Productividad", value: (p) => p.productivity_score },
  { header: "Tendencia %", value: (p) => pct(p.career_trend_pct) },
  { header: "Consistencia %", value: (p) => pct(p.consistency) },
  { header: "Composicion pts %", value: (p) => pct(p.event_share) },
  { header: "Def. equipo (goles/partido)", value: (p) => p.team_goals_conceded },
  // Raw production.
  { header: "Media pts", value: (p) => p.avg_points },
  { header: "Total pts", value: (p) => p.total_points },
  { header: "Goles", value: (p) => p.goals },
  { header: "Asistencias", value: (p) => p.assists },
  { header: "Nota Marca", value: (p) => p.marca_avg },
  { header: "Nota AS", value: (p) => p.as_avg },
  // Your own annotations, and the flags behind the risk discounts.
  {
    header: "Tags",
    value: (p) => (p.tags ?? []).map((t) => PLAYER_TAG_LABELS[t] ?? t).join(", "),
  },
  { header: "Nota", value: (p) => p.note },
  { header: "Nuevo", value: (p) => (p.is_new ? "si" : "no") },
  { header: "Cambio equipo", value: (p) => (p.team_changed ? "si" : "no") },
  { header: "Cambio posicion", value: (p) => (p.position_changed ? "si" : "no") },
  { header: "Riesgo banquillo", value: (p) => (p.is_bench_risk ? "si" : "no") },
  { header: "Ano pico", value: (p) => (p.is_peak_year ? "si" : "no") },
  { header: "Lanza penaltis", value: (p) => (p.is_penalty_taker ? "si" : "no") },
  { header: "Senal", value: (p) => p.signal },
  { header: "Motivos senal", value: (p) => (p.signal_reasons ?? []).join(" | ") },
  { header: "ID", value: (p) => p.player_id },
];

/** One cell: numbers with a decimal comma, text escaped, nullish empty. */
export function formatCell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "";
    return String(value).replace(".", ",");
  }
  // A field holding the separator, a quote or a newline has to be quoted, and
  // inner quotes doubled — a player note is free text and will do all three.
  if (/[";\r\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

export function toCsv(
  players: readonly DraftValuePlayer[],
  columns: readonly ExportColumn[] = EXPORT_COLUMNS,
): string {
  const header = columns.map((c) => formatCell(c.header)).join(SEPARATOR);
  const rows = players.map((p) => columns.map((c) => formatCell(c.value(p))).join(SEPARATOR));
  return BOM + [header, ...rows].join("\r\n") + "\r\n";
}

/** `draft-2026-2027-2026-09-10.csv` — sorts chronologically in a folder. */
export function exportFilename(seasonName: string, today = new Date()): string {
  const slug = seasonName.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const date = today.toISOString().slice(0, 10);
  return `draft-${slug || "temporada"}-${date}.csv`;
}

/** Hands the file to the browser. No-op where there is no DOM. */
export function downloadCsv(filename: string, csv: string): void {
  if (typeof document === "undefined") return;
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Freed on the next tick: revoking synchronously can cancel the download.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
