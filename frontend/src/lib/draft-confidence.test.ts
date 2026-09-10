/**
 * How much to trust a player's projection, from the signals the board already
 * carries. Backtested dispersion of real participation by profile: a settled
 * starter with history landed within 0.19 of his projection, a player with a
 * changed role or a thin sample within 0.28-0.30. The point of the indicator
 * is to make that difference visible AT the pick, so you can take the safe
 * player to fill a starting slot and the volatile one in the last rounds.
 */

import { describe, expect, it } from "vitest";

import { confidenceFor } from "./draft-confidence";

const settled = {
  seasons_played: 4,
  availability: 0.95,
  is_new: false,
  team_changed: false,
  position_changed: false,
};

describe("confidenceFor", () => {
  it("trusts a settled starter with several seasons behind him", () => {
    const c = confidenceFor(settled);
    expect(c.level).toBe("alta");
    expect(c.score).toBeGreaterThan(0.75);
  });

  it("does not trust a player with no history at all", () => {
    const c = confidenceFor({ ...settled, seasons_played: 0, is_new: true });
    expect(c.level).toBe("baja");
    expect(c.reason).toMatch(/hist[óo]rico/i);
  });

  it("names the single biggest source of doubt, not a list", () => {
    const c = confidenceFor({ ...settled, seasons_played: 1, team_changed: true });
    expect(c.reason).toBeTruthy();
    expect(c.reason).not.toMatch(/,/);
  });

  it("a changed team costs confidence — his role is unproven there", () => {
    expect(confidenceFor({ ...settled, team_changed: true }).score).toBeLessThan(
      confidenceFor(settled).score,
    );
  });

  it("a changed position costs confidence", () => {
    expect(confidenceFor({ ...settled, position_changed: true }).score).toBeLessThan(
      confidenceFor(settled).score,
    );
  });

  it("a rotating role is less predictable than a nailed-on one", () => {
    expect(confidenceFor({ ...settled, availability: 0.45 }).score).toBeLessThan(
      confidenceFor(settled).score,
    );
  });

  it("one season of history is weaker evidence than four", () => {
    expect(confidenceFor({ ...settled, seasons_played: 1 }).score).toBeLessThan(
      confidenceFor(settled).score,
    );
  });

  it("penalties accumulate — the new man who also switched position is the worst case", () => {
    const one = confidenceFor({ ...settled, team_changed: true });
    const both = confidenceFor({ ...settled, team_changed: true, position_changed: true });
    expect(both.score).toBeLessThan(one.score);
  });

  it("never leaves the 0-1 range however many penalties stack", () => {
    const c = confidenceFor({
      seasons_played: 0,
      availability: 0,
      is_new: true,
      team_changed: true,
      position_changed: true,
    });
    expect(c.score).toBeGreaterThanOrEqual(0);
    expect(c.score).toBeLessThanOrEqual(1);
  });

  it("treats an omitted flag as not flagged, which is what the API means", () => {
    // The board sends is_new/team_changed/position_changed only when true.
    expect(confidenceFor({ seasons_played: 4, availability: 0.95 })).toEqual(
      confidenceFor(settled),
    );
  });

  it("survives a player with no availability figure yet (preseason)", () => {
    const c = confidenceFor({ ...settled, availability: null });
    expect(c.score).toBeGreaterThan(0);
    expect(c.level).toBeTruthy();
  });
});
