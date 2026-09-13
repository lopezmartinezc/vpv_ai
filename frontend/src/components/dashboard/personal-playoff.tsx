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
} from "@/types";

type Props = {
  seasonId: number;
  matchdayNumber: number;
  participantId: number | null;
  scores?: MatchdayDetailResponse["scores"];
  refreshKey?: number;
  matchdayFinal?: boolean;
};

const ROUND_LABELS: Record<string, string> = {
  quarter: "Cuartos de final",
  semi: "Semifinales",
  final: "Final",
};

export function PersonalPlayoff(props: Props) {
  const [revision, setRevision] = useState(0);
  if (props.participantId === null) return null;

  return (
    <section aria-label="Tu playoff" className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>Tu playoff · Jornada {props.matchdayNumber}</h2>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.action}
            onClick={() => setRevision((value) => value + 1)}
          >
            Actualizar playoff
          </button>
          <Link className={styles.action} href={withSeason("/playoffs", props.seasonId)}>
            Ver playoffs →
          </Link>
        </div>
      </div>
      <PlayoffSeason key={`${props.seasonId}:${props.participantId}:${revision}`} {...props} />
    </section>
  );
}

function useParentRefresh(refreshKey: number | undefined, refetch: () => void) {
  const previous = useRef(refreshKey);
  useEffect(() => {
    if (previous.current !== refreshKey) refetch();
    previous.current = refreshKey;
  }, [refreshKey, refetch]);
}

function PlayoffSeason(props: Props) {
  const { data, loading, error, refetch } = useFetch<CompetitionListResponse>(
    `/competitions/season/${props.seasonId}`,
  );
  useParentRefresh(props.refreshKey, refetch);
  if (loading)
    return (
      <p role="status" className={styles.message}>
        Cargando playoff…
      </p>
    );
  if (error)
    return (
      <p role="alert" className={styles.message}>
        No se pudo cargar tu playoff. Prueba a actualizar.
      </p>
    );
  const competitions =
    data?.competitions.filter(
      (item) => item.type === "playoff" && item.season_id === props.seasonId,
    ) ?? [];
  if (!competitions.length)
    return <p className={styles.message}>Esta temporada todavía no tiene playoff.</p>;
  return (
    <div className={styles.competitions}>
      {competitions.map((competition) => (
        <PlayoffMatchups key={competition.id} {...props} competitionId={competition.id} />
      ))}
    </div>
  );
}

function PlayoffMatchups({
  competitionId,
  seasonId,
  participantId,
  matchdayNumber,
  scores,
  refreshKey,
  matchdayFinal,
}: Props & { competitionId: number }) {
  const { data, loading, error, refetch } = useFetch<CompetitionMatchupsResponse>(
    `/competitions/${competitionId}/matchups`,
  );
  useParentRefresh(refreshKey, refetch);
  if (loading)
    return (
      <p role="status" className={styles.message}>
        Cargando enfrentamiento…
      </p>
    );
  if (error || (data && data.competition.season_id !== seasonId))
    return (
      <p role="alert" className={styles.message}>
        No se pudo cargar tu enfrentamiento. Prueba a actualizar.
      </p>
    );
  const matchups =
    data?.matchups.filter(
      (matchup) =>
        matchup.matchday_number === matchdayNumber &&
        (matchup.participant_a_id === participantId || matchup.participant_b_id === participantId),
    ) ?? [];
  return (
    <div>
      <p className={styles.competition}>{data?.competition.name}</p>
      {!matchups.length && (
        <p className={styles.message}>No tienes enfrentamiento asignado en esta jornada.</p>
      )}
      {matchups.map((matchup) => {
        const isA = matchup.participant_a_id === participantId;
        // null is "not scored yet", never 0: the scoreboard shows "—" for it.
        const ownScore = isA ? matchup.score_a : matchup.score_b;
        const rivalScore = isA ? matchup.score_b : matchup.score_a;
        const rivalId = isA ? matchup.participant_b_id : matchup.participant_a_id;
        const rivalName = isA ? matchup.participant_b_name : matchup.participant_a_name;
        const rivalFeeder = isA ? matchup.feeder_b_id : matchup.feeder_a_id;
        const ownPending = scores?.find(
          (score) => score.participant_id === participantId,
        )?.pending_players;
        const rivalPending = scores?.find(
          (score) => score.participant_id === rivalId,
        )?.pending_players;
        return (
          <article key={matchup.id} className={styles.matchup}>
            <p className={styles.round}>
              {ROUND_LABELS[matchup.round_label ?? ""] ??
                matchup.round_label ??
                `Ronda ${matchup.round_number}`}
            </p>
            <div className={styles.scoreboard}>
              <div className={styles.identity}>
                <span className={styles.ownCrest} aria-hidden="true">
                  TÚ
                </span>
                <p className={styles.ownName}>Tú</p>
              </div>
              <p aria-label="Marcador del playoff" className={styles.score}>
                {ownScore ?? "—"} : {rivalScore ?? "—"}
              </p>
              <div className={styles.identity}>
                <span className={styles.rivalCrest} aria-hidden="true">
                  {rivalName
                    ?.trim()
                    .split(/\s+/)
                    .slice(0, 2)
                    .map((part) => part[0])
                    .join("")
                    .toLocaleUpperCase() || "?"}
                </span>
                <p className={styles.rivalName}>
                  {rivalName ?? (rivalFeeder !== null ? "Rival por decidir" : "Rival sin asignar")}
                </p>
              </div>
            </div>
            <p className={styles.context}>
              {ownScore === null || rivalScore === null
                ? "Marcador del playoff pendiente de actualizar; — no significa cero."
                : matchdayFinal
                  ? "Marcador registrado del playoff · jornada cerrada."
                  : "Marcador provisional del playoff."}
            </p>
            {(ownPending !== undefined || rivalPending !== undefined) && (
              <p className={styles.context}>
                Jugadores pendientes de puntuar: tú {ownPending ?? "sin datos"} · rival{" "}
                {rivalPending ?? "sin datos"}.
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
