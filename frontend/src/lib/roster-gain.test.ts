/**
 * What a pick is actually worth TO YOU.
 *
 * Prioridad ranks players in the abstract. But if your midfield is already the
 * best on the board, the 448-point midfielder replaces a 436-point one and
 * earns you twelve points, while the 390-point defender walks into an empty
 * slot and earns you all 390. The board cannot see that; only your roster can.
 *
 * "Alignable points" means: the best XI you can field under the valid
 * formations, before and after the pick.
 */

import { describe, expect, it } from "vitest";

import { bestXiPoints, rosterGain } from "./roster-gain";

const FORMATIONS = [
  { formation: "1-3-4-3", defenders: 3, midfielders: 4, forwards: 3 },
  { formation: "1-4-4-2", defenders: 4, midfielders: 4, forwards: 2 },
  { formation: "1-5-3-2", defenders: 5, midfielders: 3, forwards: 2 },
];

const p = (position: string, priority: number) => ({ position, priority });

/** A full, unremarkable squad: 1 keeper, 5 of each outfield line at 100. */
function squad() {
  return [
    p("POR", 100),
    ...Array.from({ length: 5 }, () => p("DEF", 100)),
    ...Array.from({ length: 5 }, () => p("MED", 100)),
    ...Array.from({ length: 5 }, () => p("DEL", 100)),
  ];
}

describe("bestXiPoints", () => {
  it("fields eleven and picks the formation that scores most", () => {
    // Strong forwards, weak defenders -> the 3-4-3 must win.
    const roster = [
      p("POR", 100),
      ...Array.from({ length: 5 }, () => p("DEF", 10)),
      ...Array.from({ length: 5 }, () => p("MED", 50)),
      ...Array.from({ length: 3 }, () => p("DEL", 90)),
    ];
    // 1-3-4-3: 100 + 3x10 + 4x50 + 3x90 = 600
    expect(bestXiPoints(roster, FORMATIONS)).toBe(600);
  });

  it("takes the best players in each line, not the first ones", () => {
    const roster = [
      p("POR", 100),
      p("DEF", 1), p("DEF", 99), p("DEF", 2), p("DEF", 98), p("DEF", 3),
      ...Array.from({ length: 4 }, () => p("MED", 50)),
      ...Array.from({ length: 3 }, () => p("DEL", 50)),
    ];
    // 1-3-4-3 takes the best three defenders: 99 + 98 + 3
    expect(bestXiPoints(roster, FORMATIONS)).toBe(100 + 99 + 98 + 3 + 200 + 150);
  });

  it("an incomplete squad still scores what it can field", () => {
    expect(bestXiPoints([p("POR", 100), p("DEL", 50)], FORMATIONS)).toBe(150);
  });

  it("no keeper is not a crash", () => {
    expect(bestXiPoints([p("DEL", 50)], FORMATIONS)).toBe(50);
  });

  it("an empty roster is worth nothing", () => {
    expect(bestXiPoints([], FORMATIONS)).toBe(0);
  });
});

describe("rosterGain", () => {
  it("an empty slot is worth the whole player", () => {
    const gain = rosterGain(p("DEL", 80), [p("POR", 100)], FORMATIONS);
    expect(gain).toBe(80);
  });

  it("a covered line is worth only what he adds over the man he displaces", () => {
    // Five 100-point midfielders already; a 120 one displaces a 100.
    const gain = rosterGain(p("MED", 120), squad(), FORMATIONS);
    expect(gain).toBe(20);
  });

  it("a player who would not make the XI is worth nothing today", () => {
    expect(rosterGain(p("MED", 40), squad(), FORMATIONS)).toBe(0);
  });

  it("the higher-Prioridad player is not always the better pick", () => {
    /** The whole point of the indicator. */
    const roster = [
      p("POR", 100),
      ...Array.from({ length: 5 }, () => p("MED", 200)), // midfield sorted
      p("DEF", 10), // defence bare
    ];
    const star = p("MED", 210); // higher Prioridad
    const need = p("DEF", 150); // lower Prioridad, empty slot
    expect(need.priority).toBeLessThan(star.priority);
    expect(rosterGain(need, roster, FORMATIONS)).toBeGreaterThan(
      rosterGain(star, roster, FORMATIONS),
    );
  });

  it("stops counting once a line is saturated", () => {
    // The deepest formation fields five defenders. A sixth of equal quality is
    // cover, not an upgrade, and saying so is how the indicator stops you from
    // over-drafting a line you have already filled.
    const five = [p("POR", 100), ...Array.from({ length: 5 }, () => p("DEF", 100))];
    expect(rosterGain(p("DEF", 100), five, FORMATIONS)).toBe(0);
    // Until one of them is actually better than the men in front of him.
    expect(rosterGain(p("DEF", 130), five, FORMATIONS)).toBe(30);
  });

  it("opens up a formation the squad could not field before", () => {
    // Four midfielders and one forward: the 4-4-2 is a man short up front, so
    // the best available shape is the 5-3-2, wasting a midfielder.
    const roster = [
      p("POR", 100),
      ...Array.from({ length: 5 }, () => p("DEF", 100)),
      ...Array.from({ length: 4 }, () => p("MED", 100)),
      p("DEL", 100),
    ];
    // 1-5-3-2 -> 100 + 500 + 300 + 100 = 1000 (only one forward available)
    expect(bestXiPoints(roster, FORMATIONS)).toBe(1000);
    // A second forward makes the 4-4-2 fieldable: 100 + 400 + 400 + 200 = 1100
    expect(rosterGain(p("DEL", 100), roster, FORMATIONS)).toBe(100);
  });

  it("never returns a negative gain — a pick cannot make your XI worse", () => {
    expect(rosterGain(p("DEL", 1), squad(), FORMATIONS)).toBeGreaterThanOrEqual(0);
  });

  it("a player with no projection yet contributes nothing", () => {
    expect(rosterGain({ position: "DEL", priority: null }, squad(), FORMATIONS)).toBe(0);
  });
});
