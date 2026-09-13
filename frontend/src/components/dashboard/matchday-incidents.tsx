"use client";

import Link from "next/link";
import { useState } from "react";
import { useFetch } from "@/hooks/use-fetch";
import { withSeason } from "@/lib/season-link";
import styles from "./home.module.css";
import type { RankingsResponse } from "@/types";

interface MatchdayIncidentsProps {
  seasonId: number;
  matchdayNumber: number;
  enabled: boolean;
  refreshKey?: number;
}

/**
 * Presentation only: the rankings API owns the goal/minutes rules, including
 * leaving out matches that do not count.
 */
export function MatchdayIncidents({
  seasonId,
  matchdayNumber,
  enabled,
  refreshKey = 0,
}: MatchdayIncidentsProps) {
  const [attempt, setAttempt] = useState(0);

  return (
    <section
      aria-label={`Lo que marca diferencias · Jornada ${matchdayNumber}`}
      className={`${styles.card} ${styles.incidents}`}
    >
      <div className={styles.incidentsHead}>
        <div>
          <p className={styles.cardKicker}>Las decisiones también juegan</p>
          <h2 className={styles.cardTitle}>Lo que marca diferencias · J{matchdayNumber}</h2>
        </div>
        <Link href={withSeason("/ranking", seasonId)} className={styles.textLink}>
          Ver rankings
        </Link>
      </div>
      {enabled ? (
        <IncidentsContent
          key={`${seasonId}:${matchdayNumber}:${refreshKey}:${attempt}`}
          seasonId={seasonId}
          matchdayNumber={matchdayNumber}
          onRetry={() => setAttempt((value) => value + 1)}
        />
      ) : (
        <p className="mt-3 text-sm text-vpv-text-muted">
          Las diferencias se mostrarán cuando cierre el plazo de alineación.
        </p>
      )}
    </section>
  );
}

function IncidentsContent({
  seasonId,
  matchdayNumber,
  onRetry,
}: Pick<MatchdayIncidentsProps, "seasonId" | "matchdayNumber"> & {
  onRetry: () => void;
}) {
  const { data, loading, error } = useFetch<RankingsResponse>(`/rankings/${seasonId}`);

  if (loading) {
    return (
      <p role="status" className="mt-3 text-sm text-vpv-text-muted">
        Cargando diferencias de la jornada…
      </p>
    );
  }

  if (
    error ||
    !data ||
    data.season_id !== seasonId ||
    data.burger.season_id !== seasonId ||
    data.bench.season_id !== seasonId
  ) {
    return (
      <div className="mt-3">
        <p role="alert" className="text-sm text-vpv-text-muted">
          No se pudieron cargar las diferencias de la jornada.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded border border-vpv-card-border px-3 py-2 text-sm text-vpv-text focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-vpv-accent"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const goals = data.burger.entries.flatMap((entry) =>
    entry.goals
      .filter((goal) => goal.matchday_number === matchdayNumber)
      .map((goal) => ({ ...goal, participantId: entry.participant_id, owner: entry.display_name })),
  );
  const bench = data.bench.entries.flatMap((entry) =>
    entry.players
      .filter((player) => player.matchday_number === matchdayNumber)
      .map((player) => ({
        ...player,
        participantId: entry.participant_id,
        owner: entry.display_name,
      })),
  );

  return (
    <div className={styles.incidentsGrid}>
      <div className={styles.incidentGroup} data-kind="goals">
        <h3 className={styles.incidentHeading}>
          <span className={styles.incidentIcon} aria-hidden="true">
            ↗
          </span>
          Goleadores fuera del once
        </h3>
        {goals.length === 0 ? (
          <p className="mt-2 text-sm text-vpv-text-muted">
            Sin goles fuera del once registrados en esta jornada.
          </p>
        ) : (
          <ul className={styles.incidentList}>
            {goals.map((goal) => (
              <li key={`${goal.participantId}:${goal.player_id}`} className={styles.incidentItem}>
                <span>{goal.owner}</span> {goal.player_name} · {goal.goals}{" "}
                {goal.goals === 1 ? "gol" : "goles"}
                <span className="block text-xs text-vpv-text-muted">{goal.team_name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className={styles.incidentGroup} data-kind="bench">
        <h3 className={styles.incidentHeading}>
          <span className={styles.incidentIcon} aria-hidden="true">
            —
          </span>
          Alineados que no jugaron
        </h3>
        <p className="mt-1 text-xs text-vpv-text-muted">
          Solo partidos computables con estadísticas confirmadas; no incluye jugadores pendientes de
          jugar.
        </p>
        {bench.length === 0 ? (
          <p className="mt-2 text-sm text-vpv-text-muted">
            Sin alineados sin minutos registrados en esta jornada.
          </p>
        ) : (
          <ul className={styles.incidentList}>
            {bench.map((player) => (
              <li
                key={`${player.participantId}:${player.player_id}`}
                className={styles.incidentItem}
              >
                <span>{player.owner}</span> {player.player_name}
                <span className="block text-xs text-vpv-text-muted">
                  {player.team_name} · Sin minutos
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
