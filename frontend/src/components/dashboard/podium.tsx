import Link from "next/link";
import type { StandingEntry } from "@/types";
import { withSeason } from "@/lib/season-link";
import styles from "./home.module.css";

export function Podium({
  entries,
  participantId = null,
  seasonId,
}: {
  entries: StandingEntry[];
  participantId?: number | null;
  /** The season these standings belong to; the link to the full table keeps it. */
  seasonId?: number;
}) {
  if (entries.length === 0) return null;
  return (
    <section className={`${styles.card} ${styles.general}`} aria-label="Clasificación general">
      <div className={styles.generalHead}>
        <h2>La general</h2>
        <span>{entries.length} equipos</span>
      </div>
      <ol className={styles.generalList}>
        {entries.map((entry) => (
          <li
            key={entry.participant_id}
            className={styles.generalRow}
            data-you={entry.participant_id === participantId}
          >
            <span>{entry.rank}</span>
            <span>
              {entry.display_name}
              {entry.participant_id === participantId && (
                <span className="sr-only"> · Mi equipo</span>
              )}
            </span>
            <strong>
              {entry.total_points}
              <span className="sr-only"> puntos</span>
            </strong>
          </li>
        ))}
      </ol>
      <div className={styles.generalFooter}>
        <Link className={styles.textLink} href={withSeason("/clasificacion", seasonId)}>
          Ver clasificación completa <span aria-hidden="true">→</span>
        </Link>
      </div>
    </section>
  );
}
