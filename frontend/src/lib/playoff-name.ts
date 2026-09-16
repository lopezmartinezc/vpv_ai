/**
 * What the Liga's playoffs are called, in David Silva's memory: "DAVID Cup
 * Apertura", "DAVID Cup Clausura". Renaming them is this one line (and
 * LIGA_PLAYOFF_NAME in backend/src/shared/playoff_name.py, for the chat).
 * Tournaments keep "Playoff".
 */
export const LIGA_PLAYOFF_NAME = "DAVID Cup";

export function playoffName(isTournament: boolean): string {
  return isTournament ? "Playoff" : LIGA_PLAYOFF_NAME;
}

/** "DAVID Cup Apertura" in the Liga; a tournament's playoff keeps its own name. */
export function playoffTitle(isTournament: boolean, competition: string): string {
  return isTournament ? competition : `${LIGA_PLAYOFF_NAME} ${competition}`;
}
