import { describe, it, expect } from "vitest";

import { buildSuggestions } from "@/lib/draft-suggestions";
import type { PlayerDraftStats } from "@/types";

function player(
  id: number,
  position: string,
  priority: number,
  vorp = priority,
): PlayerDraftStats {
  return {
    player_id: id,
    display_name: `P${id}`,
    team_name: "T",
    position,
    photo_path: null,
    priority,
    priority_base: priority,
    position_tier: "solid",
    vorp,
    event_share: null,
    team_goals_conceded: null,
    overall_rank: null,
    tags: [],
    is_bench_risk: false,
    is_peak_year: false,
    is_penalty_taker: false,
    is_new: false,
    team_changed: false,
    avg_pts: 0,
    matchdays_played: 0,
    starter_pct: 0,
  };
}

const pool = (list: PlayerDraftStats[]) =>
  Object.fromEntries(list.map((p) => [String(p.player_id), p]));

describe("buildSuggestions", () => {
  it("ranks by the chosen metric", () => {
    const players = pool([
      player(1, "DEL", 100, 5),
      player(2, "DEL", 200, 1),
    ]);
    expect(buildSuggestions(players, "priority", new Set())["DEL"]).toEqual([2, 1]);
    expect(buildSuggestions(players, "vorp", new Set())["DEL"]).toEqual([1, 2]);
  });

  it("drops a player as soon as he is picked", () => {
    // The bug this fixes: stats are fetched once when the page opens, so
    // without the live picked set the suggestions kept offering players
    // somebody had already taken.
    const players = pool([player(1, "DEL", 200), player(2, "DEL", 100)]);

    expect(buildSuggestions(players, "priority", new Set())["DEL"]).toEqual([1, 2]);
    expect(buildSuggestions(players, "priority", new Set([1]))["DEL"]).toEqual([2]);
  });

  it("refills from below instead of shrinking", () => {
    // Six candidates, five slots: taking the top one must promote the sixth,
    // not leave four.
    const players = pool(
      [1, 2, 3, 4, 5, 6].map((i) => player(i, "MED", 100 - i)),
    );

    expect(buildSuggestions(players, "priority", new Set())["MED"]).toEqual([
      1, 2, 3, 4, 5,
    ]);
    expect(buildSuggestions(players, "priority", new Set([1]))["MED"]).toEqual([
      2, 3, 4, 5, 6,
    ]);
  });

  it("keeps positions independent", () => {
    const players = pool([player(1, "POR", 50), player(2, "DEF", 50)]);
    const out = buildSuggestions(players, "priority", new Set([1]));
    expect(out["POR"]).toEqual([]);
    expect(out["DEF"]).toEqual([2]);
  });

  it("ignores players with no value for the chosen metric", () => {
    const players = pool([player(1, "DEL", 100)]);
    players["1"] = { ...players["1"], vorp: null };
    expect(buildSuggestions(players, "vorp", new Set())["DEL"]).toEqual([]);
    expect(buildSuggestions(players, "priority", new Set())["DEL"]).toEqual([1]);
  });

  it("always returns every position, even when empty", () => {
    const out = buildSuggestions({}, "priority", new Set());
    expect(Object.keys(out).sort()).toEqual(["DEF", "DEL", "MED", "POR"]);
  });
});
