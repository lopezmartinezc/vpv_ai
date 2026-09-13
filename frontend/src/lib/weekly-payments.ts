import type { ParticipantScore } from "@/types";

/** A season payment rule, as `/seasons/{id}/payments` returns it. */
export interface SeasonPaymentEntry {
  id: number;
  payment_type: string;
  position_rank: number | null;
  amount: number;
  description: string | null;
}

/** What each place in a matchday pays: position → euros (`weekly_position` rules). */
export function weeklyRulesFrom(payments: SeasonPaymentEntry[]): Record<number, number> {
  const rules: Record<number, number> = {};
  for (const p of payments) {
    if (p.payment_type === "weekly_position" && p.position_rank !== null) {
      rules[p.position_rank] = p.amount;
    }
  }
  return rules;
}

export interface WeeklyAmount {
  participant_id: number;
  display_name: string;
  total_points: number;
  amount: number;
}

/**
 * What each participant pays for a matchday, from its ranking and the season's
 * weekly rules. Amounts go by sequential position, not by rank (which has gaps
 * on ties), and a tie pays what the worse of the tied places pays.
 */
export function weeklyAmounts(
  scores: ParticipantScore[],
  rules: Record<number, number>,
): WeeklyAmount[] {
  const sorted = [...scores].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
  const n = sorted.length;
  if (n === 0) return [];

  const amounts = sorted.map((_, i) => Number(rules[i + 1] ?? 0));

  // Worst to best: same points, same payment.
  let prevPoints = sorted[n - 1].total_points;
  let prevAmount = amounts[n - 1];
  for (let i = n - 2; i >= 0; i--) {
    if (sorted[i].total_points > prevPoints) {
      prevPoints = sorted[i].total_points;
      prevAmount = amounts[i];
    } else {
      prevPoints = sorted[i].total_points;
      amounts[i] = prevAmount;
    }
  }

  return sorted.map((s, i) => ({
    participant_id: s.participant_id,
    display_name: s.display_name,
    total_points: s.total_points,
    amount: amounts[i],
  }));
}

/** Euros the Spanish way: "2 €", "2,50 €". */
export function formatEuros(amount: number): string {
  const decimals = Number.isInteger(amount) ? 0 : 2;
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount);
}
