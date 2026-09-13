import { describe, it, expect } from "vitest";
import { resolveSeason } from "@/contexts/season-context";
import type { SeasonSummary } from "@/types";

/**
 * Which season a screen is about, and who gets to decide.
 *
 * Admin renders a menu section per competition (⚽ Liga / 🏆 Torneo) from the
 * same item list, so both said "Jornadas" and both linked to the same place. The
 * page then chose its own season — in five of them, literally whichever the API
 * returned first. The menu could say Torneo while the screen operated on Liga.
 *
 * The URL is now the authority, because it is the only source the reader can
 * see, share and reload, and the only one that can differ between two open tabs.
 * Everything below pins that order.
 */

const season = (id: number, over: Partial<SeasonSummary> = {}): SeasonSummary =>
  ({
    id,
    name: `T${id}`,
    status: "finished",
    kind: "league",
    ...over,
  }) as SeasonSummary;

const LIGA = season(12, { status: "active", kind: "league" });
const TORNEO = season(13, { status: "active", kind: "tournament" });
const VIEJA = season(7);
const ALL = [VIEJA, LIGA, TORNEO];

describe("resolveSeason", () => {
  it("the URL beats a stored preference", () => {
    expect(resolveSeason(ALL, "13", "12")?.id).toBe(13);
  });

  it("the URL beats the active league, which is the whole point", () => {
    expect(resolveSeason(ALL, "7", null)?.id).toBe(7);
  });

  it("falls back to the stored preference when the URL is silent", () => {
    expect(resolveSeason(ALL, null, "13")?.id).toBe(13);
  });

  it("falls back to the active league when nothing is stored", () => {
    expect(resolveSeason(ALL, null, null)?.id).toBe(LIGA.id);
  });

  it("falls back to the active tournament when there is no active league", () => {
    expect(resolveSeason([VIEJA, TORNEO], null, null)?.id).toBe(TORNEO.id);
  });

  it("falls back to the first season when none is active", () => {
    expect(resolveSeason([VIEJA], null, null)?.id).toBe(VIEJA.id);
  });

  it("ignores a season id that does not exist rather than blanking the screen", () => {
    expect(resolveSeason(ALL, "999", null)?.id).toBe(LIGA.id);
    expect(resolveSeason(ALL, "no-soy-un-numero", null)?.id).toBe(LIGA.id);
  });

  it("ignores a stale stored id, which is what a deleted season leaves behind", () => {
    expect(resolveSeason(ALL, null, "999")?.id).toBe(LIGA.id);
  });

  it("returns null with no seasons at all instead of throwing", () => {
    expect(resolveSeason([], "12", "12")).toBeNull();
  });

  it("treats a missing kind as league, like the rest of the app", () => {
    const sinKind = { ...season(20, { status: "active" }), kind: undefined };
    expect(resolveSeason([sinKind as SeasonSummary], null, null)?.id).toBe(20);
  });
});
