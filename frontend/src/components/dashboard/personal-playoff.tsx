"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useFetch } from "@/hooks/use-fetch";
import { withSeason } from "@/lib/season-link";
import styles from "./personal-playoff.module.css";
import type {
  CompetitionListResponse,
  CompetitionMatchupsResponse,
  MatchdayDetailResponse,
  MatchupEntry,
} from "@/types";

/**
 * Where the matchday stands. Before the deadline there is nothing to score
 * yet, so only the rival shows; from then on, the score.
 */
export type PlayoffPhase = "before" | "during" | "final";

type Props = {
  seasonId: number;
  matchdayNumber: number;
  participantId: number | null;
  phase: PlayoffPhase;
  scores?: MatchdayDetailResponse["scores"];
  refreshKey?: number;
};

const ROUND_LABELS: Record<string, string> = {
  quarter: "Cuartos de final",
  semi: "Semifinales",
  final: "Final",
};

/**
 * Your playoff duels this matchday, sized to the moment: one line before the
 * deadline, a compact scoreboard after. Nothing at all when there is no
 * playoff or no duel for you this matchday — an empty panel on every home
 * visit weighed more than the duel itself.
 */
export function PersonalPlayoff(props: Props) {
  const [attempt, setAttempt] = useState(0);
  if (props.participantId === null) return null;
  return (
    <PlayoffSeason
      key={`${props.seasonId}:${props.participantId}:${attempt}`}
      {...props}
      onRetry={() => setAttempt((value) => value + 1)}
    />
  );
}

function useParentRefresh(refreshKey: number | undefined, refetch: () => void) {
  const previous = useRef(refreshKey);
  useEffect(() => {
    if (previous.current !== refreshKey) refetch();
    previous.current = refreshKey;
  }, [refreshKey, refetch]);
}

type Retry = { onRetry: () => void };

function Failure({ onRetry }: Retry) {
  return (
    <p role="alert" className={styles.failure}>
      No se pudo cargar tu playoff.{" "}
      <button type="button" onClick={onRetry} className={styles.retry}>
        Reintentar
      </button>
    </p>
  );
}

function PlayoffSeason({ onRetry, ...props }: Props & Retry) {
  const { data, error, refetch } = useFetch<CompetitionListResponse>(
    `/competitions/season/${props.seasonId}`,
  );
  useParentRefresh(props.refreshKey, refetch);
  if (error) return <Failure onRetry={onRetry} />;
  const competitions =
    data?.competitions.filter(
      (item) => item.type === "playoff" && item.season_id === props.seasonId,
    ) ?? [];
  return (
    <>
      {competitions.map((competition) => (
        <PlayoffDuels
          key={competition.id}
          {...props}
          competitionId={competition.id}
          onRetry={onRetry}
        />
      ))}
    </>
  );
}

function PlayoffDuels({
  competitionId,
  onRetry,
  ...props
}: Props & Retry & { competitionId: number }) {
  const { data, error, refetch } = useFetch<CompetitionMatchupsResponse>(
    `/competitions/${competitionId}/matchups`,
  );
  useParentRefresh(props.refreshKey, refetch);
  if (error || (data && data.competition.season_id !== props.seasonId)) {
    return <Failure onRetry={onRetry} />;
  }
  if (!data) return null;
  const duels = data.matchups.filter(
    (matchup) =>
      matchup.matchday_number === props.matchdayNumber &&
      (matchup.participant_a_id === props.participantId ||
        matchup.participant_b_id === props.participantId),
  );
  return (
    <>
      {duels.map((matchup) => (
        <Duel key={matchup.id} {...props} matchup={matchup} competition={data.competition.name} />
      ))}
    </>
  );
}

/** How the duel ended, from the backend's winner; a tie only with both scores in. */
function outcomeOf(
  matchup: MatchupEntry,
  participantId: number | null,
  own: number | null,
  rival: number | null,
): string | null {
  if (matchup.winner_participant_id !== null) {
    return matchup.winner_participant_id === participantId ? "Duelo ganado" : "Duelo perdido";
  }
  return own !== null && rival !== null && own === rival ? "Empate" : null;
}

function Duel({
  matchup,
  competition,
  seasonId,
  matchdayNumber,
  participantId,
  phase,
  scores,
}: Props & { matchup: MatchupEntry; competition: string }) {
  const isA = matchup.participant_a_id === participantId;
  // null is "not scored yet", never 0: the scoreboard shows "—" for it.
  const own = isA ? matchup.score_a : matchup.score_b;
  const rival = isA ? matchup.score_b : matchup.score_a;
  const rivalId = isA ? matchup.participant_b_id : matchup.participant_a_id;
  const rivalName = isA ? matchup.participant_b_name : matchup.participant_a_name;
  const rivalFeeder = isA ? matchup.feeder_b_id : matchup.feeder_a_id;
  const round =
    ROUND_LABELS[matchup.round_label ?? ""] ?? matchup.round_label ?? `Ronda ${matchup.round_number}`;
  const title = `${competition} · ${round}`;
  const label = `Tu playoff · ${competition}`;
  const link = (
    <Link className={styles.link} href={withSeason("/playoffs", seasonId)}>
      Ver playoffs
    </Link>
  );

  if (phase === "before") {
    return (
      <section aria-label={label} className={styles.line}>
        <p>
          <span className={styles.kicker}>{title}</span>{" "}
          {rivalName ? (
            <>
              tu rival: <strong>{rivalName}</strong>
            </>
          ) : rivalFeeder !== null ? (
            "rival por decidir"
          ) : (
            "sin rival asignado"
          )}
        </p>
        {link}
      </section>
    );
  }

  const ownPending = scores?.find((score) => score.participant_id === participantId)?.pending_players;
  const rivalPending = scores?.find((score) => score.participant_id === rivalId)?.pending_players;
  const outcome = phase === "final" ? outcomeOf(matchup, participantId, own, rival) : null;

  return (
    <section aria-label={label} className={styles.card}>
      <div className={styles.head}>
        <p className={styles.kicker}>
          {title} · J{matchdayNumber} · {phase === "final" ? "Final" : "Provisional"}
        </p>
        {link}
      </div>
      <p className={styles.scoreboard}>
        <span className={styles.own}>Tú</span>
        <span className={styles.score}>
          {own ?? "—"} : {rival ?? "—"}
        </span>
        <span className={styles.rival}>
          {rivalName ?? (rivalFeeder !== null ? "Por decidir" : "Sin rival")}
        </span>
      </p>
      {phase === "during" && (ownPending !== undefined || rivalPending !== undefined) && (
        <p className={styles.note}>
          Pendientes de puntuar: tú {ownPending ?? "sin datos"} · rival {rivalPending ?? "sin datos"}
        </p>
      )}
      {outcome && <p className={styles.outcome}>{outcome}</p>}
    </section>
  );
}
