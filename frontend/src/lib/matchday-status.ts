/**
 * Whether a matchday's scores are the final ones.
 *
 * Migrated seasons end in "completed"; the scraper's own end state,
 * "finished", is final only once the stats are confirmed.
 */
export function isMatchdayFinal(matchday: { status: string; stats_ok: boolean }): boolean {
  return (
    matchday.status === "completed" || (matchday.status === "finished" && matchday.stats_ok)
  );
}

/**
 * When the lineup deadline of a matchday falls, in ms, or null if unknown.
 *
 * The server's effective deadline wins, overrides included: the first kick-off
 * can be an early match played days before the rest (J6, 2026-27). Only an
 * older API that does not send it falls back to kick-off minus the margin.
 */
export function lineupDeadlineMs(
  matchday: { deadline_at?: string | null; first_match_at: string | null },
  marginMin: number,
): number | null {
  if (matchday.deadline_at !== undefined) {
    return matchday.deadline_at ? Date.parse(matchday.deadline_at) : null;
  }
  return matchday.first_match_at ? Date.parse(matchday.first_match_at) - marginMin * 60_000 : null;
}
