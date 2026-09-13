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
