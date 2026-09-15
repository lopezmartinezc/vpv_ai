import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersonalPlayoff } from "./personal-playoff";
import type { CompetitionSummary, FinalSeries, MatchupEntry } from "@/types";

const apertura: CompetitionSummary = {
  id: 7,
  season_id: 1,
  name: "Apertura",
  type: "playoff",
  status: "ko",
};

const leg = (id: number, matchday: number, over: Partial<MatchupEntry> = {}): MatchupEntry => ({
  id,
  phase: "ko",
  group_label: null,
  round_label: "final",
  round_number: 13 + id,
  matchday_id: 100 + id,
  matchday_number: matchday,
  participant_a_id: 10,
  participant_a_name: "Ana",
  participant_b_id: 20,
  participant_b_name: "Luis",
  feeder_a_id: 1,
  feeder_b_id: 2,
  score_a: null,
  score_b: null,
  winner_participant_id: null,
  winner_name: null,
  ...over,
});

const legs = [
  leg(1, 19, { score_a: 60, score_b: 50, winner_participant_id: 10, winner_name: "Ana" }),
  leg(2, 20),
  leg(3, 21),
];

const series = (over: Partial<FinalSeries> = {}): FinalSeries => ({
  participant_a_id: 10,
  participant_a_name: "Ana",
  participant_b_id: 20,
  participant_b_name: "Luis",
  wins_a: 1,
  wins_b: 0,
  winner_participant_id: null,
  winner_name: null,
  legs: legs.map((m) => ({
    matchup_id: m.id,
    matchday_number: m.matchday_number,
    score_a: m.score_a,
    score_b: m.score_b,
    result: m.id === 1 ? "a" : "pending",
    decided_by: m.id === 1 ? "points" : null,
  })),
  ...over,
});

function serve(final: FinalSeries) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const body = input.endsWith("/season/1")
        ? { season_id: 1, competitions: [apertura] }
        : { competition: apertura, matchups: legs, final_series: final };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PersonalPlayoff in a final over three jornadas", () => {
  it("says which jornada of the final it is and how the series stands, from your side", async () => {
    serve(series());
    render(<PersonalPlayoff seasonId={1} matchdayNumber={20} participantId={20} phase="before" />);
    expect(await screen.findByText(/Jornada 2 de 3 · vas 0-1/)).toBeInTheDocument();
    expect(screen.getByText(/tu rival:/)).toHaveTextContent("Apertura · Final tu rival: Ana");
  });

  it("once the final is settled, says so on the jornada left over", async () => {
    serve(series({ wins_a: 2, winner_participant_id: 10, winner_name: "Ana" }));
    render(<PersonalPlayoff seasonId={1} matchdayNumber={21} participantId={10} phase="final" />);
    expect(await screen.findByText("Final decidida: ¡eres campeón!")).toBeInTheDocument();
  });
});
