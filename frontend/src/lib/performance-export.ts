/**
 * Which columns of the performance tables travel to a spreadsheet.
 *
 * Two lenses over the same season, exported separately because they answer
 * different questions: "Jugadores" is what happened (goals, cards, minutes,
 * marks), "Avanzado" is how reliably it happened (spread, percentiles,
 * confidence interval, form). Both carry derived figures the tables compute
 * on the fly and would otherwise be lost — minutes per match, starts as a
 * share of appearances, consistency as 1−CV.
 */

import type { AdvancedPlayerStat, PlayerStatRow } from "@/types";
import type { ExportColumn } from "./csv-export";
import { asPercent, exportFilename as buildFilename, toCsv as buildCsv } from "./csv-export";

/** A share as a percentage, or nothing when there is nothing to divide by. */
const share = (part: number, whole: number): number | null =>
  whole > 0 ? Math.round((part / whole) * 1000) / 10 : null;

/** An average per match, to one decimal. */
const perMatch = (total: number, matches: number): number | null =>
  matches > 0 ? Math.round((total / matches) * 10) / 10 : null;

export const PLAYER_COLUMNS: ExportColumn<PlayerStatRow>[] = [
  { header: "Jugador", value: (p) => p.display_name },
  { header: "Equipo", value: (p) => p.team_name },
  { header: "Posicion", value: (p) => p.position },
  { header: "Partidos jugados", value: (p) => p.matchdays_played },
  { header: "Titularidades", value: (p) => p.started_count },
  // Derived on screen, and the reason two players with the same PJ are not
  // the same player.
  { header: "Titular %", value: (p) => share(p.started_count, p.matchdays_played) },
  { header: "Minutos", value: (p) => p.minutes_played },
  { header: "Minutos por partido", value: (p) => perMatch(p.minutes_played, p.matchdays_played) },
  { header: "Goles", value: (p) => p.goals },
  { header: "Goles de penalti", value: (p) => p.penalty_goals },
  { header: "Goles en propia", value: (p) => p.own_goals },
  { header: "Asistencias", value: (p) => p.assists },
  { header: "Penaltis parados", value: (p) => p.penalties_saved },
  { header: "Tarjetas amarillas", value: (p) => p.yellow_cards },
  { header: "Tarjetas rojas", value: (p) => p.red_cards },
  { header: "Nota Marca", value: (p) => p.avg_marca },
  { header: "Nota AS", value: (p) => p.avg_as },
  { header: "Media pts", value: (p) => p.avg_points },
  { header: "Total pts", value: (p) => p.total_points },
  { header: "ID", value: (p) => p.player_id },
];

export const ADVANCED_COLUMNS: ExportColumn<AdvancedPlayerStat>[] = [
  { header: "Jugador", value: (p) => p.display_name },
  { header: "Equipo", value: (p) => p.team_name },
  { header: "Posicion", value: (p) => p.position },
  { header: "Partidos jugados", value: (p) => p.matchdays_played },
  { header: "Minutos", value: (p) => p.minutes_played },
  { header: "Media pts", value: (p) => p.avg_points },
  { header: "Total pts", value: (p) => p.total_points },
  { header: "Pts por 90 min", value: (p) => p.pp90 },
  { header: "Desviacion estandar", value: (p) => p.std_dev },
  { header: "Coef. variacion", value: (p) => p.cv },
  // The table shows consistency as 1−CV; exporting only CV would invert the
  // reading of the column people actually use.
  { header: "Consistencia %", value: (p) => asPercent(1 - p.cv) },
  { header: "Suelo (P10)", value: (p) => p.p10 },
  { header: "Mediana (P50)", value: (p) => p.p50 },
  { header: "Techo (P90)", value: (p) => p.p90 },
  { header: "IC95 inferior", value: (p) => p.ci_lower },
  { header: "IC95 superior", value: (p) => p.ci_upper },
  { header: "Forma (ultimos 5)", value: (p) => p.form_5 },
  { header: "Tendencia", value: (p) => p.trend },
  { header: "ID", value: (p) => p.player_id },
];

export function playersToCsv(rows: readonly PlayerStatRow[]): string {
  return buildCsv(rows, PLAYER_COLUMNS);
}

export function advancedToCsv(rows: readonly AdvancedPlayerStat[]): string {
  return buildCsv(rows, ADVANCED_COLUMNS);
}

export function performanceFilename(
  lens: "rendimiento" | "avanzado",
  seasonName: string,
  today = new Date(),
): string {
  return buildFilename(lens, seasonName, today);
}
