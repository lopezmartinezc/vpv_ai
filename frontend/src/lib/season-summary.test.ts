import { describe, expect, it } from "vitest";

import type { SeasonLine } from "@/types";
import { formatSeasonLine } from "./season-summary";

const season: SeasonLine = {
  season_name: "2025-2026",
  games_played: 30,
  goals: 12,
  assists: 5,
  total_points: 210,
  avg_points: 7,
  marca_avg: 6.8,
  as_avg: 2.4,
};

describe("formatSeasonLine", () => {
  it("carries the production a drafter is looking for", () => {
    const line = formatSeasonLine(season);
    expect(line).toContain("30 PJ");
    expect(line).toContain("12 goles");
    expect(line).toContain("5 asist.");
    expect(line).toContain("210 pts");
  });

  it("states the average per match, not only the total", () => {
    expect(formatSeasonLine(season)).toContain("media 7.0/partido");
  });

  it("carries both press marks — AS was missing and it is half the media score", () => {
    const line = formatSeasonLine(season);
    expect(line).toContain("Marca 6.8");
    expect(line).toContain("AS 2.4");
  });

  it("omits a mark that does not exist rather than printing a zero", () => {
    const line = formatSeasonLine({ ...season, as_avg: null, marca_avg: null });
    expect(line).not.toContain("AS");
    expect(line).not.toContain("Marca");
    expect(line).toContain("12 goles");
  });

  it("keeps one mark when only the other is missing", () => {
    expect(formatSeasonLine({ ...season, marca_avg: null })).toContain("AS 2.4");
    expect(formatSeasonLine({ ...season, as_avg: null })).toContain("Marca 6.8");
  });

  it("reads as one line with a single separator style", () => {
    expect(formatSeasonLine(season).split(" · ")).toHaveLength(7);
  });
});
