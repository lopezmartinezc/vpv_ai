import { formatEuros, weeklyAmounts } from "@/lib/weekly-payments";
import type { MatchdayDetailResponse, ParticipantScore, StandingEntry } from "@/types";
import styles from "./home.module.css";

/**
 * What you pay for the matchday: "if it ended now" while it is being played,
 * the real thing once it is final. Nothing without weekly payments, and
 * nothing before there is a ranking — with no stats yet everyone is tied.
 */
export function moneyLine(
  scores: ParticipantScore[],
  participantId: number,
  rules: Record<number, number> | undefined,
  final: boolean,
): { text: string; pays: boolean } | null {
  if (!rules || Object.keys(rules).length === 0) return null;
  const mine = scores.find((s) => s.participant_id === participantId);
  if (!mine || mine.rank === null) return null;
  const amount =
    weeklyAmounts(scores, rules).find((e) => e.participant_id === participantId)?.amount ?? 0;
  const pays = amount > 0;
  if (final) return { pays, text: pays ? `Pagas ${formatEuros(amount)}` : "No pagas" };
  return {
    pays,
    text: `Si acabara ahora: ${pays ? `pagas ${formatEuros(amount)}` : "no pagas"}`,
  };
}

/** Your place in the general table, and how far you are from the top. */
export function generalLine(standings: StandingEntry[], participantId: number): string | null {
  const me = standings.find((e) => e.participant_id === participantId);
  const others = standings.filter((e) => e.participant_id !== participantId);
  if (!me || others.length === 0) return null;
  const best = Math.max(...others.map((e) => e.total_points));
  if (me.total_points > best) return `Líder · +${me.total_points - best} sobre el 2.º`;
  if (me.total_points === best) {
    return me.rank === 1
      ? "Líder, empatado a puntos"
      : `General: ${me.rank}.º · empatado con el líder`;
  }
  return `General: ${me.rank}.º · a ${best - me.total_points} pts del líder`;
}

/**
 * Where you stand in the matchday being followed: your place, points and
 * players still to score, what you would pay, and your place in the table.
 */
export function YourMatchday({
  matchday,
  participantId,
  standings,
  weeklyRules,
  final,
}: {
  matchday: MatchdayDetailResponse;
  participantId: number;
  standings: StandingEntry[];
  weeklyRules?: Record<number, number>;
  final: boolean;
}) {
  const score = matchday.scores.find((s) => s.participant_id === participantId);
  // A matchday that does not count charges nobody.
  const money = matchday.counts
    ? moneyLine(matchday.scores, participantId, weeklyRules, final)
    : null;
  const general = generalLine(standings, participantId);

  return (
    <section className={styles.yourDay} aria-label={`Tu jornada · J${matchday.number}`}>
      <p className={styles.yourDayTitle}>Tu jornada · J{matchday.number}</p>
      {score ? (
        <p className={styles.yourDayMain}>
          <span>
            <strong>{score.rank !== null ? `${score.rank}.º` : "—"}</strong> de{" "}
            {matchday.scores.length}
          </span>
          <span>
            <strong>{score.total_points}</strong> pts
          </span>
          <span>
            <span aria-hidden="true">◷</span> {score.pending_players} por puntuar
          </span>
        </p>
      ) : (
        <p className={styles.yourDayMain}>Sin puntuación en la J{matchday.number}.</p>
      )}
      {money && (
        <p className={styles.yourDayMoney} data-pays={money.pays}>
          {money.text}
        </p>
      )}
      {general && <p className={styles.yourDayGeneral}>{general}</p>}
    </section>
  );
}
