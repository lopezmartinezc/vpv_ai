import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { generalLine, moneyLine, YourMatchday } from "./your-matchday";
import type { MatchdayDetailResponse, ParticipantScore, StandingEntry } from "@/types";

const score = (participant_id: number, rank: number | null, total_points: number, pending = 0) =>
  ({
    participant_id,
    rank,
    total_points,
    display_name: `P${participant_id}`,
    formation: null,
    pending_players: pending,
  }) as ParticipantScore;

const standing = (participant_id: number, rank: number, total_points: number) =>
  ({ participant_id, rank, total_points, display_name: `P${participant_id}` }) as StandingEntry;

const RULES = { 1: 0, 2: 1, 3: 2 };
const SCORES = [score(1, 1, 50), score(2, 2, 34, 4), score(3, 3, 20)];

describe("moneyLine", () => {
  it("says what you would pay while the matchday is on", () => {
    expect(moneyLine(SCORES, 2, RULES, false)).toEqual({
      text: "Si acabara ahora: pagas 1 €",
      pays: true,
    });
    expect(moneyLine(SCORES, 1, RULES, false)?.text).toBe("Si acabara ahora: no pagas");
  });

  it("says what you pay once it is final", () => {
    expect(moneyLine(SCORES, 3, RULES, true)?.text).toBe("Pagas 2 €");
    expect(moneyLine(SCORES, 1, RULES, true)?.text).toBe("No pagas");
  });

  it("says nothing in a season without weekly payments", () => {
    expect(moneyLine(SCORES, 2, undefined, false)).toBeNull();
    expect(moneyLine(SCORES, 2, {}, false)).toBeNull();
  });

  it("says nothing before there is a ranking", () => {
    expect(moneyLine([score(1, null, 0), score(2, null, 0)], 2, RULES, false)).toBeNull();
  });
});

describe("generalLine", () => {
  const table = [standing(1, 1, 120), standing(2, 2, 115), standing(3, 3, 108)];

  it("gives your place and how far the leader is", () => {
    expect(generalLine(table, 3)).toBe("General: 3.º · a 12 pts del líder");
  });

  it("gives the leader's margin over the second", () => {
    expect(generalLine(table, 1)).toBe("Líder · +5 sobre el 2.º");
  });

  it("does not invent a margin in a tie", () => {
    const tied = [standing(1, 1, 120), standing(2, 1, 120)];
    expect(generalLine(tied, 1)).toBe("Líder, empatado a puntos");
    expect(generalLine([standing(1, 1, 120), standing(2, 2, 120)], 2)).toBe(
      "General: 2.º · empatado con el líder",
    );
  });

  it("says nothing without you in the table", () => {
    expect(generalLine(table, 9)).toBeNull();
  });
});

describe("YourMatchday", () => {
  const matchday = { number: 5, counts: true, scores: SCORES } as MatchdayDetailResponse;

  it("never charges for a matchday that does not count", () => {
    render(
      <YourMatchday
        matchday={{ ...matchday, counts: false }}
        participantId={2}
        standings={[]}
        weeklyRules={RULES}
        final={false}
      />,
    );
    expect(screen.getByRole("region")).not.toHaveTextContent("pagas");
  });

  it("shows your place, points and players still to score", () => {
    render(
      <YourMatchday matchday={matchday} participantId={2} standings={[]} final={false} />,
    );
    const card = screen.getByRole("region", { name: "Tu jornada · J5" });
    expect(card).toHaveTextContent("2.º de 3");
    expect(card).toHaveTextContent("34 pts");
    expect(card).toHaveTextContent("4 por puntuar");
    expect(card).not.toHaveTextContent("pagas");
  });

  it("writes a dash, never 0, for a place not ranked yet", () => {
    const early = { number: 5, scores: [score(2, null, 0, 11)] } as MatchdayDetailResponse;
    render(<YourMatchday matchday={early} participantId={2} standings={[]} final={false} />);
    expect(screen.getByRole("region")).toHaveTextContent("— de 1");
  });

  it("adds the money and the general table when there are", () => {
    render(
      <YourMatchday
        matchday={matchday}
        participantId={2}
        standings={[standing(1, 1, 120), standing(2, 2, 115)]}
        weeklyRules={RULES}
        final={false}
      />,
    );
    expect(screen.getByText("Si acabara ahora: pagas 1 €")).toHaveAttribute("data-pays", "true");
    expect(screen.getByText("General: 2.º · a 5 pts del líder")).toBeInTheDocument();
  });

  it("says so when you have no score in the matchday", () => {
    render(<YourMatchday matchday={matchday} participantId={9} standings={[]} final={false} />);
    expect(screen.getByRole("region")).toHaveTextContent("Sin puntuación en la J5.");
  });
});
