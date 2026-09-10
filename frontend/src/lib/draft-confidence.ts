/**
 * How much to trust a player's projection.
 *
 * Two players can both project 180 points and be completely different bets:
 * one has four seasons in the same role at the same club, the other arrived in
 * August and has played three matches. The board showed them identically until
 * now, which is exactly when it matters least to be vague — at the pick.
 *
 * Backtested dispersion of real participation against the projection, by
 * profile: a settled starter landed within 0.19, a player with a thin sample or
 * a changed role within 0.28-0.30. The penalties below are ordered by that
 * measurement; their exact sizes are a judgement, so the indicator is a
 * three-step scale rather than a false-precision percentage.
 *
 * Use it to take the safe player when you are filling a starting slot and the
 * volatile one in the last rounds, where the downside is a bench place.
 */

export type ConfidenceLevel = "alta" | "media" | "baja";

export interface Confidence {
  level: ConfidenceLevel;
  /** 0-1. Only meaningful as an ordering; do not read it as a probability. */
  score: number;
  /** The single biggest source of doubt, for the tooltip. */
  reason: string;
}

/** The fields of a board row the estimate needs.
 *
 *  The flags are optional because the API omits them when false; a missing
 *  flag means "not flagged", never "unknown", so treating it as false is the
 *  same answer the server would have given. */
export interface ConfidenceInput {
  seasons_played: number;
  availability?: number | null;
  is_new?: boolean | null;
  team_changed?: boolean | null;
  position_changed?: boolean | null;
}

/** A rotating role is the least predictable thing about a player short of
 *  having no record at all — measured dispersion 0.27 against 0.19. */
const ROTATION_AVAILABILITY = 0.8;

interface Penalty {
  applies: boolean;
  cost: number;
  reason: string;
}

function penalties(p: ConfidenceInput): Penalty[] {
  const avail = p.availability ?? null;
  return [
    {
      applies: p.is_new === true || p.seasons_played === 0,
      // Enough on its own to reach the bottom band: no league record was the
      // widest-dispersion profile measured (0.30), worse than any other single
      // factor, and nothing about the current season narrows it.
      cost: 0.55,
      reason: "sin histórico en la liga",
    },
    {
      applies: p.is_new !== true && p.seasons_played === 1,
      cost: 0.2,
      reason: "una sola temporada de historial",
    },
    {
      applies: p.is_new !== true && p.seasons_played === 2,
      cost: 0.1,
      reason: "solo dos temporadas de historial",
    },
    {
      applies: p.team_changed === true,
      cost: 0.2,
      reason: "cambió de equipo: su rol allí está sin probar",
    },
    {
      applies: p.position_changed === true,
      cost: 0.15,
      reason: "cambió de posición",
    },
    {
      applies: avail !== null && avail < ROTATION_AVAILABILITY,
      cost: 0.2,
      reason: "rol rotatorio: no es titular fijo",
    },
  ];
}

export function confidenceFor(p: ConfidenceInput): Confidence {
  const active = penalties(p).filter((x) => x.applies);
  const raw = active.reduce((acc, x) => acc - x.cost, 1);
  const score = Math.min(1, Math.max(0, raw));

  // One reason, the costliest. A list of five caveats is not a tooltip anyone
  // reads mid-draft; the biggest one is what changes the decision.
  const worst = active.reduce<Penalty | null>(
    (best, x) => (best === null || x.cost > best.cost ? x : best),
    null,
  );

  const level: ConfidenceLevel = score >= 0.75 ? "alta" : score >= 0.5 ? "media" : "baja";
  return { level, score, reason: worst?.reason ?? "historial estable y rol definido" };
}

/** Three filled dots for high, one for low — readable at a glance in a table. */
export function confidenceDots(level: ConfidenceLevel): string {
  return level === "alta" ? "●●●" : level === "media" ? "●●○" : "●○○";
}
