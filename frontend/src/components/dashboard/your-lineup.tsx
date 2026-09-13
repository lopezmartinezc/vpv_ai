"use client";

import { useEffect, useRef } from "react";
import { useFetch } from "@/hooks/use-fetch";
import type { LineupDetailResponse } from "@/types";
import { LineupPlayers } from "./matchday-accordion";
import styles from "./home.module.css";

/**
 * Your own eleven for the matchday being followed, open without a click:
 * during a matchday the first question is who is still to score. Your own
 * lineup is always readable to you, before the deadline too.
 */
export function YourLineup({
  seasonId,
  matchdayNumber,
  participantId,
  refreshKey = 0,
}: {
  seasonId: number;
  matchdayNumber: number;
  participantId: number;
  refreshKey?: number;
}) {
  const { data, loading, error, errorStatus, refetch } = useFetch<LineupDetailResponse>(
    `/matchdays/${seasonId}/${matchdayNumber}/lineup/${participantId}`,
  );
  const previous = useRef(refreshKey);
  useEffect(() => {
    if (previous.current !== refreshKey) refetch();
    previous.current = refreshKey;
  }, [refreshKey, refetch]);

  return (
    <section className={`${styles.card} ${styles.yourLineup}`} aria-label={`Tu once · J${matchdayNumber}`}>
      <div className={styles.yourLineupHead}>
        <h2 className={styles.cardTitle}>Tu once · J{matchdayNumber}</h2>
        {data && <span className={styles.yourLineupTotal}>{data.total_points} pts</span>}
      </div>
      {loading && (
        <p role="status" className={styles.yourLineupNote}>
          Cargando tu once…
        </p>
      )}
      {!loading && errorStatus === 404 && (
        <p className={styles.yourLineupNote}>No alineaste en la J{matchdayNumber}.</p>
      )}
      {!loading && error && errorStatus !== 404 && (
        <p role="alert" className={styles.yourLineupNote}>
          No se pudo cargar tu once.{" "}
          <button type="button" onClick={refetch} className="min-h-11 text-vpv-accent">
            Reintentar
          </button>
        </p>
      )}
      {data && <LineupPlayers lineup={data} compact />}
    </section>
  );
}
