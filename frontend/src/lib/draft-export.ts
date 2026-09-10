/**
 * Which columns of the draft board travel to a spreadsheet, and how.
 *
 * Everything goes, including the model scores the table hides behind
 * "+ Columnas" and the fields it has no room for at all — the point of
 * exporting is to have what the screen cannot show. The CSV machinery itself
 * lives in csv-export, shared with the performance tables.
 */

import type { DraftValuePlayer } from "@/types";
import type { ExportColumn } from "./csv-export";
import { asPercent, exportFilename as buildFilename, toCsv as buildCsv } from "./csv-export";
import { confidenceFor } from "./draft-confidence";
import { PLAYER_TAG_LABELS } from "./player-tags";

export const EXPORT_COLUMNS: ExportColumn<DraftValuePlayer>[] = [
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
  { header: "Participacion %", value: (p) => asPercent(p.participation) },
  { header: "Jornadas restantes est.", value: (p) => p.exp_games_remaining },
  { header: "Disponibilidad %", value: (p) => asPercent(p.availability) },
  { header: "Partidos jugados", value: (p) => p.games_played },
  { header: "Temporadas", value: (p) => p.seasons_played },
  // Model scores — hidden behind "+ Columnas" on screen, always exported.
  { header: "Ensemble", value: (p) => p.ensemble_score },
  { header: "Media simple", value: (p) => p.simple_avg },
  { header: "Forma 2a mitad", value: (p) => p.second_half_score },
  { header: "Estabilidad", value: (p) => p.stability_score },
  { header: "Productividad", value: (p) => p.productivity_score },
  { header: "Tendencia %", value: (p) => asPercent(p.career_trend_pct) },
  { header: "Consistencia %", value: (p) => asPercent(p.consistency) },
  { header: "Composicion pts %", value: (p) => asPercent(p.event_share) },
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

export function toCsv(players: readonly DraftValuePlayer[]): string {
  return buildCsv(players, EXPORT_COLUMNS);
}

export function exportFilename(seasonName: string, today = new Date()): string {
  return buildFilename("draft", seasonName, today);
}

export { downloadCsv } from "./csv-export";
