import { describe, it, expect } from "vitest";

import {
  BIG_TEAMS,
  MAX_KEEPERS,
  ROSTER_TARGET,
  simulateDraft,
  type SimOptions,
} from "@/lib/draft-simulator";
import type { DraftValuePlayer } from "@/types";

let nextId = 1;
function p(
  position: string,
  team: string,
  priority: number,
  extra: Partial<DraftValuePlayer> = {},
): DraftValuePlayer {
  const id = nextId++;
  return {
    player_id: id,
    slug: `p${id}`,
    display_name: `${position}-${team}-${priority}`,
    team_name: team,
    position,
    photo_path: null,
    priority,
    priority_base: priority,
    vorp: priority / 10,
    tags: [],
    is_drafted: false,
    ...extra,
  } as DraftValuePlayer;
}

/** A pool deep enough for a full 11 x 26 draft (22 POR / 88 DEF / 77 MED / 66 DEL). */
function pool(): DraftValuePlayer[] {
  nextId = 1;
  const teams = ["Real Madrid", "Barcelona", "Atlético", "Alavés", "Getafe", "Celta"];
  const depth: Record<string, number> = { POR: 30, DEF: 100, MED: 90, DEL: 80 };
  const out: DraftValuePlayer[] = [];
  for (const [pos, n] of Object.entries(depth)) {
    for (let i = 0; i < n; i++) {
      out.push(p(pos, teams[i % teams.length], 300 - i * 2));
    }
  }
  return out;
}

const opts = (over: Partial<SimOptions> = {}): SimOptions => ({
  participants: 11,
  myPosition: 5,
  rounds: 26,
  seed: 42,
  bigTeamBias: 0.2,
  myOrder: "priority",
  ...over,
});

describe("simulateDraft", () => {
  it("follows the snake order", () => {
    const r = simulateDraft(pool(), opts({ participants: 4, rounds: 2 }));
    const round1 = r.picks.slice(0, 4).map((x) => x.participantId);
    const round2 = r.picks.slice(4, 8).map((x) => x.participantId);
    expect(round1).toEqual([1, 2, 3, 4]);
    expect(round2).toEqual([4, 3, 2, 1]); // reversed
  });

  it("never drafts the same player twice", () => {
    const r = simulateDraft(pool(), opts());
    const ids = r.picks.map((x) => x.player.player_id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("is reproducible for a given seed, and different for another", () => {
    const a = simulateDraft(pool(), opts({ seed: 7 }));
    const b = simulateDraft(pool(), opts({ seed: 7 }));
    const c = simulateDraft(pool(), opts({ seed: 8 }));
    const names = (r: ReturnType<typeof simulateDraft>) =>
      r.picks.map((x) => x.player.display_name).join(",");
    expect(names(a)).toBe(names(b));
    expect(names(a)).not.toBe(names(c));
  });

  it("builds a plausible squad shape for every participant", () => {
    // The targets sum to 23 of 26, so they are soft: the last picks go to the
    // best available. What must hold is that nobody ends up with an absurd
    // shape — four keepers, or a position left empty.
    const r = simulateDraft(pool(), opts());
    for (const squad of r.squads) {
      expect(squad.players.length).toBe(26);
      const n = (pos: string) => squad.players.filter((x) => x.position === pos).length;
      expect(n("POR")).toBeGreaterThanOrEqual(1);
      expect(n("POR")).toBeLessThanOrEqual(MAX_KEEPERS);
      for (const pos of ["DEF", "MED", "DEL"]) {
        expect(n(pos)).toBeGreaterThanOrEqual(ROSTER_TARGET[pos] - 2);
      }
    }
  });

  it("gives me the picks belonging to my draft slot", () => {
    const r = simulateDraft(pool(), opts({ myPosition: 5, participants: 11 }));
    // Snake, 11 players: slot 5 picks #5, then #18 (11*2 - 5 + 1).
    expect(r.myPicks.map((x) => x.pickNumber).slice(0, 2)).toEqual([5, 18]);
    expect(r.myPicks.every((x) => x.participantId === 5)).toBe(true);
  });

  // --- the league's observed behaviour -------------------------------------

  it("sends a big-team keeper in the first round", () => {
    // Observed: "un portero de equipo grande seguro que sale en primera ronda".
    const r = simulateDraft(pool(), opts({ participants: 11 }));
    const firstRound = r.picks.filter((x) => x.round === 1);
    const bigKeeper = firstRound.find(
      (x) => x.player.position === "POR" && BIG_TEAMS.some((t) => x.player.team_name.includes(t)),
    );
    expect(bigKeeper).toBeDefined();
  });

  it("handcuffs: whoever takes a keeper ends up with his team-mate", () => {
    // Observed: the same manager takes the backup in the last rounds so the
    // goal of a top team is covered.
    const r = simulateDraft(pool(), opts());
    const withTwo = r.squads.filter(
      (s) => s.players.filter((x) => x.position === "POR").length >= 2,
    );
    expect(withTwo.length).toBeGreaterThan(0);
    // The first two keepers a manager takes should be team-mates.
    const handcuffed = withTwo.filter((s) => {
      const keepers = s.players.filter((x) => x.position === "POR");
      return keepers[0].team_name === keepers[1].team_name;
    });
    expect(handcuffed.length / withTwo.length).toBeGreaterThan(0.5);
  });

  it("bots overvalue big-team players when the bias is on", () => {
    // Observed: "es muy dificil elegir al del Alaves aunque Prio lo ponga
    // arriba, porque el de equipo top te da mas confianza".
    const bigShare = (bias: number) => {
      const r = simulateDraft(pool(), opts({ bigTeamBias: bias, rounds: 3 }));
      const big = r.picks.filter((x) =>
        BIG_TEAMS.some((t) => x.player.team_name.includes(t)),
      ).length;
      return big / r.picks.length;
    };
    expect(bigShare(0.4)).toBeGreaterThan(bigShare(0));
  });

  it("my own picks follow my chosen order, not the crowd's bias", () => {
    const r = simulateDraft(pool(), opts({ myOrder: "priority" }));
    // Each of my picks must be the best available by priority at that moment,
    // among positions I still need.
    const first = r.myPicks[0];
    const takenBefore = new Set(
      r.picks.filter((x) => x.pickNumber < first.pickNumber).map((x) => x.player.player_id),
    );
    const bestAvailable = pool()
      .filter((x) => !takenBefore.has(x.player_id))
      .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))[0];
    expect(first.player.priority).toBe(bestAvailable.priority);
  });

  it("reports what fell to me at each of my turns", () => {
    const r = simulateDraft(pool(), opts());
    expect(r.myPicks.length).toBe(26);
    expect(r.squads.find((s) => s.isMe)?.players.length).toBe(26);
    expect(r.exhausted).toBe(false);
  });

  it("flags a pool too shallow to finish instead of silently stopping", () => {
    // A real board can genuinely run out of keepers before 26 rounds; the UI
    // has to say so rather than present a short draft as if it were complete.
    const thin = pool().filter((x) => x.position !== "MED");
    const r = simulateDraft(thin, opts());
    expect(r.exhausted).toBe(true);
  });
});

describe("players the board cannot value", () => {
  it("reports them instead of dropping them silently", () => {
    // A star missing from the simulated draft looks like a broken simulator.
    // It is usually a gap in the board — a roster not yet synced, or a player
    // with no projection — and the UI has to be able to say so.
    const noPrio = { ...p("DEL", "Barcelona", 0), display_name: "Sin proyección" };
    (noPrio as { priority: number | null }).priority = null;
    const r = simulateDraft([...pool(), noPrio], opts());

    expect(r.picks.some((x) => x.player.display_name === "Sin proyección")).toBe(false);
    expect(r.excluded.map((x) => x.player.display_name)).toContain("Sin proyección");
    expect(r.excluded[0].reason).toBe("sin-prioridad");
  });

  it("reports nothing when every player has a value", () => {
    expect(simulateDraft(pool(), opts()).excluded).toEqual([]);
  });
});

describe("players with a value but no position", () => {
  it("reports the top of the board when positions have not been synced", () => {
    // The real report: the six best by Prioridad were never picked and nothing
    // said why. Their position was empty, so no slot could hold them.
    const orphan = p("", "Barcelona", 999);
    orphan.display_name = "Estrella sin posición";
    const r = simulateDraft([...pool(), orphan], opts());

    expect(r.picks.some((x) => x.player.display_name === "Estrella sin posición")).toBe(
      false,
    );
    const row = r.excluded.find((x) => x.player.display_name === "Estrella sin posición");
    expect(row?.reason).toBe("sin-posicion");
  });
});

describe("players already owned", () => {
  const owned = () => {
    const x = p("DEL", "Barcelona", 999);
    x.display_name = "Fichado en la prueba";
    (x as { is_drafted: boolean }).is_drafted = true;
    return x;
  };

  it("drafts the whole pool by default, ignoring leftover ownership", () => {
    // Ownership left over from a rehearsal draft was quietly removing the best
    // players: the simulation started at the 8th by Prioridad and nothing said
    // why. A planning tool has to work from the full pool.
    const r = simulateDraft([...pool(), owned()], opts());
    expect(r.picks.some((x) => x.player.display_name === "Fichado en la prueba")).toBe(
      true,
    );
    expect(r.excluded).toEqual([]);
  });

  it("reports them by name when asked to respect ownership", () => {
    const r = simulateDraft([...pool(), owned()], opts({ ignoreDrafted: false }));
    expect(r.picks.some((x) => x.player.display_name === "Fichado en la prueba")).toBe(
      false,
    );
    expect(r.excluded[0]).toMatchObject({ reason: "ya-fichado" });
  });
});
