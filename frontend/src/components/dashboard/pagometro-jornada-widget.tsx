import type { ParticipantScore } from "@/types";

interface PaymentEntry {
  participant_id: number;
  display_name: string;
  total_points: number;
  amount: number;
}

/**
 * Compute weekly payment amounts from matchday rankings using
 * configurable rules from season_payments (weekly_position).
 * Tie adjustment: same points = same (worse) payment.
 */
function computeWeeklyAmounts(
  scores: ParticipantScore[],
  rules: Record<number, number>,
): PaymentEntry[] {
  const sorted = [...scores].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
  const n = sorted.length;
  if (n === 0) return [];

  // Base amounts by sequential position (1-based index),
  // NOT by rank (which has gaps on ties, e.g. 1,2,3,3,5...)
  const amounts = sorted.map((_, i) => Number(rules[i + 1] ?? 0));

  // Tie adjustment: worst to best, same points = same payment
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

export function PagometroJornadaWidget({
  scores,
  matchdayNumber,
  weeklyRules,
}: {
  scores: ParticipantScore[];
  matchdayNumber: number;
  weeklyRules: Record<number, number>;
}) {
  const entries = computeWeeklyAmounts(scores, weeklyRules);
  if (entries.length === 0) return null;

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
        Pagometro J{matchdayNumber}
      </h2>

      <div className="mt-3 space-y-1.5">
        {entries.map((entry) => (
          <div
            key={entry.participant_id}
            className="flex items-center gap-3"
          >
            <span className="min-w-0 flex-1 truncate text-sm text-vpv-text">
              {entry.display_name}
            </span>
            <span className="text-xs tabular-nums text-vpv-text-muted">
              {entry.total_points} pts
            </span>
            <span
              className={`w-14 text-right text-sm font-bold tabular-nums ${
                entry.amount > 0 ? "text-red-400" : "text-green-400"
              }`}
            >
              {entry.amount > 0 ? `${entry.amount.toFixed(2)} €` : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
