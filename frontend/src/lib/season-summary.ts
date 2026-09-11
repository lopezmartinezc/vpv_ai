/**
 * One season's production as a single readable line.
 *
 * Extracted from the draft row so it can be tested: the expanded detail is
 * where a proven scorer read "Goles: 0" because nothing said which season the
 * figures belonged to, and a display bug there is invisible until it misleads
 * someone mid-draft.
 */

import type { SeasonLine } from "@/types";

/** Marca is in stars and AS in picas; both are averages per match. */
export function formatSeasonLine(season: SeasonLine): string {
  const parts = [
    `${season.games_played} PJ`,
    `${season.goals} goles`,
    `${season.assists} asist.`,
    `${season.total_points.toFixed(0)} pts`,
    `media ${season.avg_points.toFixed(1)}/partido`,
  ];
  if (season.marca_avg != null) parts.push(`Marca ${season.marca_avg.toFixed(1)}`);
  if (season.as_avg != null) parts.push(`AS ${season.as_avg.toFixed(1)}`);
  return parts.join(" · ");
}
