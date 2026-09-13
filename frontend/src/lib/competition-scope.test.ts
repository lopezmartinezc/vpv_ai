import { describe, expect, it } from "vitest";
import { appliesToCompetition } from "@/lib/competition-scope";

describe("appliesToCompetition", () => {
  it("keeps the Copa to leagues (IN-04)", () => {
    expect(appliesToCompetition("/copa", false)).toBe(true);
    expect(appliesToCompetition("/copa", true)).toBe(false);
  });

  it("keeps the tournament pages to tournaments", () => {
    for (const path of ["/grupos", "/bracket", "/playoffs", "/predicciones"]) {
      expect(appliesToCompetition(path, true)).toBe(true);
      expect(appliesToCompetition(path, false)).toBe(false);
    }
  });

  it("lets every other page apply to both", () => {
    for (const path of ["/", "/clasificacion", "/jornadas", "/ranking", "/economia"]) {
      expect(appliesToCompetition(path, true)).toBe(true);
      expect(appliesToCompetition(path, false)).toBe(true);
    }
  });

  it("reads the path, not the query or the hash", () => {
    expect(appliesToCompetition("/copa?season=3", true)).toBe(false);
    expect(appliesToCompetition("/copa#grupo", true)).toBe(false);
  });
});
