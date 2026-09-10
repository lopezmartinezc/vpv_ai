import { describe, it, expect } from "vitest";

import { fixtureDifficulty } from "@/lib/fixture-difficulty";

const wideOpen = { opponent_attack: 2.0, opponent_defence: 1.7 };
const shutDown = { opponent_attack: 0.8, opponent_defence: 0.9 };

describe("fixtureDifficulty", () => {
  it("grades keepers and defenders on what the opponent scores", () => {
    expect(fixtureDifficulty("POR", wideOpen)).toBe("dificil");
    expect(fixtureDifficulty("POR", shutDown)).toBe("facil");
    expect(fixtureDifficulty("DEF", wideOpen)).toBe("dificil");
  });

  it("grades midfielders and forwards on what the opponent concedes", () => {
    expect(fixtureDifficulty("DEL", wideOpen)).toBe("facil");
    expect(fixtureDifficulty("DEL", shutDown)).toBe("dificil");
    expect(fixtureDifficulty("MED", wideOpen)).toBe("facil");
  });

  it("reads the same fixture opposite ways for a keeper and a forward", () => {
    // A side that scores freely and concedes freely: the whole reason a single
    // difficulty number cannot work.
    expect(fixtureDifficulty("POR", wideOpen)).toBe("dificil");
    expect(fixtureDifficulty("DEL", wideOpen)).toBe("facil");
  });

  it("returns null when there is no fixture rather than guessing", () => {
    expect(fixtureDifficulty("POR", null)).toBeNull();
    expect(fixtureDifficulty("POR", undefined)).toBeNull();
  });

  it("returns null for a position it does not grade", () => {
    expect(fixtureDifficulty("", wideOpen)).toBeNull();
  });
});
