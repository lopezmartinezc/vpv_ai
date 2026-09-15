/**
 * Which pages belong to only one kind of competition.
 *
 * The menu hid the Copa in a tournament while the home still offered it, and
 * the Copa page then refused (IN-04): two lists, two answers. Both read this
 * table now. A route not listed applies to leagues and tournaments alike —
 * like /playoffs: a tournament's single playoff, the Liga's Apertura and
 * Clausura.
 */
export type CompetitionKind = "league" | "tournament";

const ONLY_IN: Record<string, CompetitionKind> = {
  "/palmares": "league",
  "/copa": "league",
  "/grupos": "tournament",
  "/bracket": "tournament",
  "/predicciones": "tournament",
};

export function appliesToCompetition(href: string, isTournament: boolean): boolean {
  const only = ONLY_IN[href.split(/[?#]/)[0]];
  return !only || only === (isTournament ? "tournament" : "league");
}
