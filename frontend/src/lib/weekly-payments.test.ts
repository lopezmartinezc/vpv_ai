import { describe, expect, it } from "vitest";
import {
  formatEuros,
  weeklyAmounts,
  weeklyRulesFrom,
  type SeasonPaymentEntry,
} from "@/lib/weekly-payments";
import type { ParticipantScore } from "@/types";

const score = (participant_id: number, rank: number | null, total_points: number) =>
  ({
    participant_id,
    rank,
    total_points,
    display_name: `P${participant_id}`,
    formation: null,
    pending_players: 0,
  }) as ParticipantScore;

const RULES = { 1: 0, 2: 1, 3: 2, 4: 3 };
const paid = (scores: ParticipantScore[], rules: Record<number, number> = RULES) =>
  Object.fromEntries(weeklyAmounts(scores, rules).map((e) => [e.participant_id, e.amount]));

describe("weeklyRulesFrom", () => {
  it("keeps only the weekly position rules", () => {
    const payments = [
      { id: 1, payment_type: "weekly_position", position_rank: 1, amount: 0 },
      { id: 2, payment_type: "weekly_position", position_rank: 4, amount: 3 },
      { id: 3, payment_type: "initial_fee", position_rank: null, amount: 50 },
      { id: 4, payment_type: "weekly_position", position_rank: null, amount: 9 },
      { id: 5, payment_type: "final_position", position_rank: 2, amount: 100 },
    ] as SeasonPaymentEntry[];
    expect(weeklyRulesFrom(payments)).toEqual({ 1: 0, 4: 3 });
  });
});

describe("weeklyAmounts", () => {
  it("charges each place what its position pays", () => {
    expect(paid([score(1, 1, 50), score(2, 2, 40), score(3, 3, 30), score(4, 4, 20)])).toEqual({
      1: 0,
      2: 1,
      3: 2,
      4: 3,
    });
  });

  it("makes a tie pay what the worse of the tied places pays", () => {
    expect(paid([score(1, 1, 50), score(2, 2, 30), score(3, 2, 30), score(4, 4, 20)])).toEqual({
      1: 0,
      2: 2,
      3: 2,
      4: 3,
    });
  });

  it("goes by position, not by rank, when ranks have gaps", () => {
    expect(paid([score(1, 1, 50), score(2, 5, 40)])).toEqual({ 1: 0, 2: 1 });
  });

  it("charges nothing for a place without a rule", () => {
    expect(paid([score(1, 1, 50), score(2, 2, 40)], { 1: 0 })).toEqual({ 1: 0, 2: 0 });
  });

  it("returns nothing without scores", () => {
    expect(weeklyAmounts([], RULES)).toEqual([]);
  });
});

describe("formatEuros", () => {
  it("writes euros the Spanish way", () => {
    expect(formatEuros(2)).toBe("2 €");
    expect(formatEuros(2.5)).toBe("2,50 €");
  });
});
