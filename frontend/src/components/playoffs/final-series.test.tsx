import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  FinalSeriesView,
  defaultPlayoff,
  legOutcome,
  seriesLine,
} from "./final-series";
import type { CompetitionSummary, FinalLeg, FinalSeries } from "@/types";

const playoff = (id: number, name: string, status: string): CompetitionSummary => ({
  id,
  season_id: 12,
  name,
  type: "playoff",
  status,
});

const leg = (matchup_id: number, over: Partial<FinalLeg> = {}): FinalLeg => ({
  matchup_id,
  matchday_number: 18 + matchup_id,
  score_a: null,
  score_b: null,
  result: "pending",
  decided_by: null,
  ...over,
});

const series = (over: Partial<FinalSeries> = {}): FinalSeries => ({
  participant_a_id: 1,
  participant_a_name: "Ana",
  participant_b_id: 2,
  participant_b_name: "Bea",
  wins_a: 0,
  wins_b: 0,
  winner_participant_id: null,
  winner_name: null,
  legs: [leg(1), leg(2), leg(3)],
  ...over,
});

describe("defaultPlayoff", () => {
  it("opens the playoff being played, else the last finished, else the first", () => {
    const apertura = playoff(1, "Apertura", "completed");
    const clausura = playoff(2, "Clausura", "regular");
    expect(defaultPlayoff([apertura, clausura])).toBe(clausura);
    expect(defaultPlayoff([apertura, playoff(2, "Clausura", "pending")])).toBe(apertura);
    expect(defaultPlayoff([playoff(1, "Apertura", "pending"), playoff(2, "Clausura", "pending")])?.name).toBe(
      "Apertura",
    );
    expect(defaultPlayoff([])).toBeNull();
  });
});

describe("the final as a series", () => {
  it("says how each jornada was won, including a draw settled later", () => {
    const s = series();
    expect(legOutcome(s, leg(1, { score_a: 60, score_b: 50, result: "a", decided_by: "points" }))).toBe(
      "Gana Ana",
    );
    expect(legOutcome(s, leg(2, { score_a: 45, score_b: 45 }))).toBe(
      "Empate: se decide con las otras jornadas",
    );
    expect(legOutcome(s, leg(2, { score_a: 45, score_b: 45, result: "b", decided_by: "difference" }))).toBe(
      "Empate: para Bea por diferencia",
    );
    expect(legOutcome(s, leg(3, { result: "a", decided_by: "seed" }))).toBe(
      "Empate: para Ana por clasificación",
    );
    expect(legOutcome(s, leg(3, { result: "not_needed" }))).toBe("No se disputa");
    expect(legOutcome(s, leg(3))).toBe("Pendiente");
  });

  it("tells a finalist where the series stands, from their side", () => {
    const s = series({ wins_a: 1 });
    expect(seriesLine(s, 2, 1)).toBe("Jornada 2 de 3 · vas 1-0");
    expect(seriesLine(s, 2, 2)).toBe("Jornada 2 de 3 · vas 0-1");
    expect(seriesLine(s, 99, 1)).toBeNull();
    expect(seriesLine(null, 2, 1)).toBeNull();
    const won = series({ wins_a: 2, winner_participant_id: 1, winner_name: "Ana" });
    expect(seriesLine(won, 3, 1)).toBe("Final decidida: ¡eres campeón!");
    expect(seriesLine(won, 3, 2)).toBe("Final decidida: campeón Ana");
  });

  it("shows the jornadas won, each jornada and the champion", () => {
    render(
      <FinalSeriesView
        series={series({
          wins_a: 2,
          winner_participant_id: 1,
          winner_name: "Ana",
          legs: [
            leg(1, { score_a: 60, score_b: 50, result: "a", decided_by: "points" }),
            leg(2, { score_a: 55, score_b: 40, result: "a", decided_by: "points" }),
            leg(3, { score_a: 30, score_b: 90, result: "not_needed" }),
          ],
        })}
      />,
    );
    expect(screen.getByText("Final · al mejor de 3")).toBeInTheDocument();
    expect(screen.getByLabelText("Jornadas ganadas 2 a 0")).toHaveTextContent("2 — 0");
    expect(screen.getByText("No se disputa")).toBeInTheDocument();
    expect(screen.queryByText("30 — 90")).not.toBeInTheDocument();
    expect(screen.getByText("Campeón: Ana")).toBeInTheDocument();
  });
});
