"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
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

/** How many incidents a group shows before "Ver los N". */
const VISIBLE = 3;

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

/** A list that shows the first few and the rest on request, in place. */
function Expandable<T>({
  items,
  keyOf,
  render,
}: {
  items: T[];
  keyOf: (item: T) => string;
  render: (item: T) => ReactNode;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, VISIBLE);
  return (
    <>
      <ul className={styles.incidentList}>
        {shown.map((item) => (
          <li key={keyOf(item)} className={styles.incidentItem}>
            {render(item)}
          </li>
        ))}
      </ul>
      {!all && items.length > VISIBLE && (
        <button type="button" className={styles.textLink} onClick={() => setAll(true)}>
          Ver los {items.length}
        </button>
      )}
    </>
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
            🍔
          </span>
          Goleadores fuera del once
        </h3>
        {goals.length === 0 ? (
          <p className="mt-2 text-sm text-vpv-text-muted">
            Sin goles fuera del once registrados en esta jornada.
          </p>
        ) : (
          <Expandable
            items={goals}
            keyOf={(goal) => `${goal.participantId}:${goal.player_id}`}
            render={(goal) => (
              <>
                <span>{goal.owner}</span> {goal.player_name} · {goal.goals}{" "}
                {goal.goals === 1 ? "gol" : "goles"}
                <span className="block text-xs text-vpv-text-muted">{goal.team_name}</span>
              </>
            )}
          />
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
          <Expandable
            items={bench}
            keyOf={(player) => `${player.participantId}:${player.player_id}`}
            render={(player) => (
              <>
                <span>{player.owner}</span> {player.player_name}
                <span className="block text-xs text-vpv-text-muted">
                  {player.team_name} · Sin minutos
                </span>
              </>
            )}
          />
        )}
      </div>
    </div>
  );
}
