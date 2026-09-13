import type { MatchdayState } from "@/types";

/**
 * A jornada's state, turned into the list of things still missing — each one
 * pointing at the screen that fixes it.
 *
 * The audit's complaint (2.3) is that resolving a jornada means coordinating
 * six independent tools by hand: Jornadas, Scraping, Notas Periódicos,
 * Alineaciones, Economía and Telegram. Nobody needs those merged into one giant
 * screen; they need to be told which of them to open, and why. That is all this
 * does — every number here comes from the backend, never from a guess made here.
 */
export type Gap = {
  id: string;
  label: string;
  /** How many items are outstanding. Zero means the gap is closed. */
  count: number;
  /** The first few, named, so the panel says *which* rather than how many. */
  examples: string[];
  /** The tool that resolves it, already carrying the season. */
  href: string;
  /** Whether this is what stands between the jornada and closing. */
  blocking: boolean;
};

const EXAMPLES_SHOWN = 4;

export function gapsOf(state: MatchdayState): Gap[] {
  const season = `?season=${state.season_id}`;
  const all: Gap[] = [
    {
      id: "sin-resultado",
      label: "Partidos sin resultado",
      count: state.matches_without_result.length,
      examples: state.matches_without_result,
      href: `/admin/jornadas${season}`,
      blocking: true,
    },
    {
      id: "sin-stats",
      label: "Partidos sin estadísticas",
      count: state.matches_without_stats.length,
      examples: state.matches_without_stats,
      href: `/admin/scraping`,
      blocking: true,
    },
    {
      id: "sin-alineacion",
      label: "Participantes sin alineación",
      count: state.lineups_missing.length,
      examples: state.lineups_missing,
      // Not blocking on purpose: a participant who does not field a side still
      // scores zero, and the jornada closes without him. It is worth seeing, not
      // worth stopping for.
      href: `/admin/alineaciones${season}`,
      blocking: false,
    },
    {
      id: "sin-notas",
      label: "Jugadores sin nota de periódico",
      count: state.ratings_missing,
      examples: [],
      href: `/admin/marca${season}`,
      blocking: false,
    },
    {
      id: "errores-scraping",
      label: "Errores del último scraping",
      count: state.scrape_errors.length,
      examples: state.scrape_errors,
      href: `/admin/scraping`,
      blocking: false,
    },
  ];
  return all.filter((gap) => gap.count > 0);
}

export function shownExamples(gap: Gap): string[] {
  return gap.examples.slice(0, EXAMPLES_SHOWN);
}

export function hiddenExampleCount(gap: Gap): number {
  return Math.max(0, gap.examples.length - EXAMPLES_SHOWN);
}

/**
 * Whether the close button may be pressed.
 *
 * The server decides, not this. `can_close` is computed there alongside the
 * blockers, so a panel that disagreed with the API would only be lying to the
 * person pressing the button.
 */
export function closeAllowed(state: MatchdayState): boolean {
  return state.can_close;
}

/**
 * Whether closing pays money out, which is what decides how hard the
 * confirmation should be. §6 asks for confirmation proportional to risk, and
 * generating the weekly payments is the only step here that moves money.
 */
export function closeMovesMoney(state: MatchdayState): boolean {
  return state.preview.steps.some(
    (step) => step.name.toLowerCase().includes("pago") && step.outcome === "hecho",
  );
}

/** One line saying where the jornada stands, for the panel header. */
export function headline(state: MatchdayState): string {
  if (state.status === "finished") return "Jornada cerrada";
  if (state.can_close) return "Lista para cerrar";
  const blocking = gapsOf(state).filter((g) => g.blocking);
  if (blocking.length === 0) return "En curso";
  const total = blocking.reduce((n, g) => n + g.count, 0);
  return `Faltan ${total} ${total === 1 ? "cosa" : "cosas"} para poder cerrar`;
}
