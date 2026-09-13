import { describe, it, expect } from "vitest";
import {
  closeAllowed,
  closeMovesMoney,
  gapsOf,
  headline,
  hiddenExampleCount,
  shownExamples,
} from "@/features/matchday-center/gaps";
import type { MatchdayState } from "@/types";

/**
 * The panel turns a jornada's state into "what do I still have to do".
 *
 * Everything it says has to come from the backend. A panel that worked out for
 * itself whether a jornada could close would eventually disagree with the API,
 * and the person it misleads is the one about to press a button that pays money
 * out. So these tests pin the derivation, and pin that the decision itself is
 * relayed rather than recomputed.
 */

const base: MatchdayState = {
  season_id: 12,
  matchday_number: 6,
  matchday_id: 300,
  status: "pending",
  counts: true,
  stats_ok: false,
  deadline_at: null,
  is_current: true,
  matches_total: 10,
  matches_counting: 10,
  matches_without_result: [],
  matches_without_stats: [],
  participants_total: 13,
  lineups_missing: [],
  ratings_missing: 0,
  last_scrape_at: null,
  scrape_errors: [],
  blockers: [],
  can_close: true,
  preview: {
    season_id: 12,
    matchday_number: 6,
    dry_run: true,
    closed: true,
    blockers: [],
    steps: [],
  },
};

const withState = (over: Partial<MatchdayState>): MatchdayState => ({ ...base, ...over });

describe("gapsOf", () => {
  it("says nothing when there is nothing to say", () => {
    expect(gapsOf(base)).toEqual([]);
  });

  it("carries the season in every link, so the tool opens on the right one", () => {
    const gaps = gapsOf(
      withState({
        matches_without_result: ["Celta - Málaga"],
        lineups_missing: ["Carlos"],
        ratings_missing: 3,
      }),
    );
    const seasonScoped = gaps.filter((g) => g.href.startsWith("/admin/jornadas")
      || g.href.startsWith("/admin/alineaciones")
      || g.href.startsWith("/admin/marca"));
    expect(seasonScoped).not.toHaveLength(0);
    for (const gap of seasonScoped) expect(gap.href).toContain("season=12");
  });

  it("only matches block closing; a missing lineup does not", () => {
    const gaps = gapsOf(
      withState({
        matches_without_result: ["Celta - Málaga"],
        matches_without_stats: ["Getafe - Deportivo"],
        lineups_missing: ["Carlos", "Ana"],
        ratings_missing: 7,
        scrape_errors: ["timeout"],
      }),
    );
    const blocking = gaps.filter((g) => g.blocking).map((g) => g.id);
    expect(blocking.sort()).toEqual(["sin-resultado", "sin-stats"]);
  });

  it("names who and which, not just how many", () => {
    const [gap] = gapsOf(withState({ lineups_missing: ["Carlos", "Ana"] }));
    expect(gap.count).toBe(2);
    expect(gap.examples).toEqual(["Carlos", "Ana"]);
  });

  it("trims a long list and says how many it hid", () => {
    const many = ["a", "b", "c", "d", "e", "f"];
    const [gap] = gapsOf(withState({ lineups_missing: many }));
    expect(shownExamples(gap)).toHaveLength(4);
    expect(hiddenExampleCount(gap)).toBe(2);
  });
});

describe("closeAllowed", () => {
  it("relays the server's decision rather than recomputing it", () => {
    // Deliberately contradictory: blockers present but the server said yes.
    // The panel must not start arguing with the API.
    expect(closeAllowed(withState({ can_close: true, blockers: ["algo"] }))).toBe(true);
    expect(closeAllowed(withState({ can_close: false, blockers: [] }))).toBe(false);
  });
});

describe("closeMovesMoney", () => {
  const step = (name: string, outcome: string) => ({ name, outcome, detail: "" });

  it("is true when closing would generate the weekly payments", () => {
    const state = withState({
      preview: { ...base.preview, steps: [step("Generar los pagos semanales", "hecho")] },
    });
    expect(closeMovesMoney(state)).toBe(true);
  });

  it("is false when the payments are already there", () => {
    const state = withState({
      preview: { ...base.preview, steps: [step("Generar los pagos semanales", "ya_estaba")] },
    });
    expect(closeMovesMoney(state)).toBe(false);
  });

  it("is false when no step touches money", () => {
    const state = withState({
      preview: { ...base.preview, steps: [step("Evaluar los logros", "hecho")] },
    });
    expect(closeMovesMoney(state)).toBe(false);
  });
});

describe("headline", () => {
  it("says a closed jornada is closed, whatever else is outstanding", () => {
    expect(headline(withState({ status: "finished", ratings_missing: 9 }))).toBe(
      "Jornada cerrada",
    );
  });

  it("says it is ready when the server says it can close", () => {
    expect(headline(base)).toBe("Lista para cerrar");
  });

  it("counts only what actually blocks, and agrees with itself in the singular", () => {
    expect(
      headline(
        withState({ can_close: false, matches_without_result: ["Celta - Málaga"] }),
      ),
    ).toBe("Faltan 1 cosa para poder cerrar");
    expect(
      headline(
        withState({
          can_close: false,
          matches_without_result: ["A - B"],
          matches_without_stats: ["C - D"],
          ratings_missing: 40,
        }),
      ),
    ).toBe("Faltan 2 cosas para poder cerrar");
  });

  it("falls back to 'En curso' when nothing blocks but the server still says no", () => {
    expect(headline(withState({ can_close: false }))).toBe("En curso");
  });
});
