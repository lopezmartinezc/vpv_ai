import { describe, expect, it } from "vitest";
import { canAddToPosition, countsByPosition } from "./positions";
import type { SquadPlayerEntry, ValidFormation } from "@/types";

const FORMATIONS: ValidFormation[] = [
  { id: 1, formation: "1-4-3-3", defenders: 4, midfielders: 3, forwards: 3 },
  { id: 2, formation: "1-5-3-2", defenders: 5, midfielders: 3, forwards: 2 },
];

function player(id: number, position: string): SquadPlayerEntry {
  return {
    player_id: id,
    display_name: `P${id}`,
    photo_path: null,
    position,
    team_name: "T",
    season_points: 0,
    recent_form: null,
  };
}

describe("countsByPosition", () => {
  it("counts each position of the selection", () => {
    const counts = countsByPosition([player(1, "POR"), player(2, "DEF"), player(3, "DEF")]);
    expect(counts).toEqual({ POR: 1, DEF: 2, MED: 0, DEL: 0 });
  });
});

describe("canAddToPosition", () => {
  const none = { POR: 0, DEF: 0, MED: 0, DEL: 0 };

  it("allows one goalkeeper only", () => {
    expect(canAddToPosition("POR", none, FORMATIONS, 0)).toBe(true);
    expect(canAddToPosition("POR", { ...none, POR: 1 }, FORMATIONS, 1)).toBe(false);
  });

  it("stops at eleven", () => {
    expect(canAddToPosition("DEF", none, FORMATIONS, 11)).toBe(false);
  });

  it("refuses a player no formation could still fit", () => {
    expect(canAddToPosition("DEF", { ...none, DEF: 5 }, FORMATIONS, 6)).toBe(false);
    expect(canAddToPosition("DEL", { ...none, DEL: 3 }, FORMATIONS, 4)).toBe(false);
    expect(canAddToPosition("DEL", { ...none, DEF: 5, DEL: 1 }, FORMATIONS, 7)).toBe(true);
    expect(canAddToPosition("DEL", { ...none, DEF: 5, DEL: 2 }, FORMATIONS, 8)).toBe(false);
  });
});
