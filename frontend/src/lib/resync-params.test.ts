import { describe, expect, it } from "vitest";

import { resyncQuery, resyncWarning } from "./resync-params";

describe("resyncQuery", () => {
  it("sends the whole season when no matchday is given", () => {
    const q = resyncQuery({ seasonId: 12, repin: true });
    expect(q).toContain("season_id=12");
    expect(q).toContain("repin=true");
    expect(q).not.toContain("start=");
  });

  it("limits to the transfer matchday onward when one is given", () => {
    expect(resyncQuery({ seasonId: 12, repin: true, fromMatchday: "3" })).toContain("start=3");
  });

  it("ignores whitespace, empty and nonsense rather than sending start=NaN", () => {
    for (const value of ["", "   ", "abc", "0", "-2", "2.5"]) {
      expect(resyncQuery({ seasonId: 12, repin: true, fromMatchday: value })).not.toContain("start");
    }
  });

  it("carries repin=false for a points-only re-sync", () => {
    expect(resyncQuery({ seasonId: 12, repin: false })).toContain("repin=false");
  });
});

describe("resyncWarning", () => {
  it("names the range when there is one, and says the rest is left alone", () => {
    const text = resyncWarning("Adrià Pedrosa", "3");
    expect(text).toContain("jornada 3 en adelante");
    expect(text).toContain("anteriores se quedan");
  });

  it("warns about the unbounded case, which is the one that loses history", () => {
    const text = resyncWarning("Adrià Pedrosa");
    expect(text).toContain("TODAS");
    expect(text).toMatch(/desde qué jornada/);
  });

  it("names the player, so a misclick on the wrong row is visible", () => {
    expect(resyncWarning("Adrià Pedrosa", "3")).toContain("Adrià Pedrosa");
  });
});
