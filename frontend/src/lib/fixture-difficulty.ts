/**
 * How hard a fixture is — which depends on the position being asked about.
 *
 * Measured over the 8 real seasons of the league, points lost by facing the
 * hardest instead of the easiest opponent:
 *
 * | Pos | by the opponent's ATTACK | by the opponent's DEFENCE |
 * |-----|--------------------------|---------------------------|
 * | POR | 2.58                     | 1.62                      |
 * | DEF | 1.55                     | 1.40                      |
 * | MED | 1.16                     | 1.57                      |
 * | DEL | 1.43                     | 2.04                      |
 *
 * A keeper wants an opponent who cannot score; a forward wants one who cannot
 * defend. The same fixture can be easy for one and hard for the other, so a
 * single difficulty number would be wrong for somebody. Thresholds mirror
 * `backend/src/features/stats/fixtures.py`.
 */

export type Difficulty = "facil" | "media" | "dificil";

const HARD_ATTACK = 1.7;
const EASY_ATTACK = 1.2;
const EASY_DEFENCE = 1.5;
const HARD_DEFENCE = 1.1;

/** Positions graded on what the opponent scores, rather than what it concedes. */
const GRADED_ON_ATTACK = new Set(["POR", "DEF"]);

export interface OpponentStrength {
  opponent_attack: number;
  opponent_defence: number;
}

export function fixtureDifficulty(
  position: string,
  fixture: OpponentStrength | null | undefined,
): Difficulty | null {
  if (!fixture) return null;
  const pos = position.toUpperCase();
  if (GRADED_ON_ATTACK.has(pos)) {
    if (fixture.opponent_attack >= HARD_ATTACK) return "dificil";
    if (fixture.opponent_attack < EASY_ATTACK) return "facil";
    return "media";
  }
  if (pos === "MED" || pos === "DEL") {
    if (fixture.opponent_defence >= EASY_DEFENCE) return "facil";
    if (fixture.opponent_defence < HARD_DEFENCE) return "dificil";
    return "media";
  }
  return null;
}

export const DIFFICULTY_STYLE: Record<Difficulty, string> = {
  facil: "bg-emerald-500/15 text-emerald-300",
  media: "bg-vpv-border/40 text-vpv-text-muted",
  dificil: "bg-red-500/15 text-red-300",
};

export const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  facil: "Fácil",
  media: "Media",
  dificil: "Difícil",
};

export function difficultyTitle(
  position: string,
  fixture: OpponentStrength,
  difficulty: Difficulty,
): string {
  const pos = position.toUpperCase();
  const what = GRADED_ON_ATTACK.has(pos)
    ? `el rival marca ${fixture.opponent_attack.toFixed(2)} goles/partido`
    : `el rival encaja ${fixture.opponent_defence.toFixed(2)} goles/partido`;
  return `${DIFFICULTY_LABEL[difficulty]} para ${pos}: ${what}`;
}
