"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useFetch } from "@/hooks/use-fetch";
import { appliesToCompetition } from "@/lib/competition-scope";
import { isMatchdayFinal } from "@/lib/matchday-status";
import { withSeason } from "@/lib/season-link";
import type {
  CopaFullResponse,
  EconomyResponse,
  GroupStandingsResponse,
  MatchdayDetailResponse,
  MyLineupResponse,
  StandingEntry,
} from "@/types";
import { LeagueSummary } from "./league-summary";
import { MatchdayAccordion } from "./matchday-accordion";
import { MatchdayIncidents } from "./matchday-incidents";
import { PersonalPlayoff, type PlayoffPhase } from "./personal-playoff";
import { Podium } from "./podium";
import { YourLineup } from "./your-lineup";
import { YourMatchday } from "./your-matchday";
import styles from "./home.module.css";

/**
 * Whether the lineup deadline has passed. Only the server's effective deadline
 * counts (overrides included): the first kick-off can be an early match played
 * days before the rest. No deadline, or an unreadable one, is "unknown".
 */
export function isDeadlinePassed(
  deadlineAt: string | null | undefined,
  now: number,
): boolean | null {
  if (!deadlineAt) return null;
  const time = Date.parse(deadlineAt);
  return Number.isFinite(time) ? now >= time : null;
}

export function CompetitiveHome({
  seasonId,
  seasonName = "Liga VPV",
  economyEnabled = false,
  isTournament = false,
  weeklyRules,
  copa = null,
  economy = null,
  groups = null,
  current,
  previous,
  authenticated,
  standings,
  onRefresh,
}: {
  seasonId: number;
  seasonName?: string;
  economyEnabled?: boolean;
  /** Tournaments have no Copa: the shortcuts follow the same rule as the menu. */
  isTournament?: boolean;
  /** Position → euros for the weekly payments; absent when the season has none. */
  weeklyRules?: Record<number, number>;
  /** For the one-line summary of the rest of the league. */
  copa?: CopaFullResponse | null;
  economy?: EconomyResponse | null;
  groups?: GroupStandingsResponse | null;
  /** The season's current matchday: the one whose lineup is being set. */
  current: MatchdayDetailResponse;
  previous: MatchdayDetailResponse | null;
  authenticated: boolean;
  standings: StandingEntry[];
  onRefresh: () => void;
}) {
  const me = useFetch<MyLineupResponse>(
    authenticated ? `/lineups/${seasonId}/${current.number}/me` : null,
  );
  const [refreshKey, setRefreshKey] = useState(0);
  const refreshMe = me.refetch;
  // The home asks again every minute on its own; a button for it only took room.
  const refresh = useCallback(() => {
    refreshMe();
    onRefresh();
    setRefreshKey((value) => value + 1);
  }, [refreshMe, onRefresh]);
  useEffect(() => {
    const timer = setInterval(refresh, 60_000);
    return () => clearInterval(timer);
  }, [refresh]);
  const subscribe = useCallback((callback: () => void) => {
    const timer = setInterval(callback, 1_000);
    return () => clearInterval(timer);
  }, []);
  const passed = useSyncExternalStore(
    subscribe,
    () => isDeadlinePassed(current.deadline_at, Date.now()),
    () => null,
  );
  const final = isMatchdayFinal(current);
  const showCurrent = passed === true || final;
  // The matchday in play: until the current one's deadline, the previous one —
  // closed or still being played — while you set the lineup for the current.
  // A previous matchday that does not count (pre-season) is not followed: the
  // home goes straight to the one being set.
  const displayed = showCurrent ? current : previous?.counts ? previous : null;
  // The playoff follows the same matchday: a duel still being played, or else
  // the next rival.
  const playoff: { number: number; phase: PlayoffPhase; scores?: MatchdayDetailResponse["scores"] } =
    showCurrent
      ? { number: current.number, phase: final ? "final" : "during", scores: current.scores }
      : displayed && !isMatchdayFinal(displayed)
        ? { number: displayed.number, phase: "during", scores: displayed.scores }
        : { number: current.number, phase: "before" };
  const personal = authenticated ? me.data : null;
  const participantId = personal?.participant_id ?? null;
  const confirmed = personal?.current_lineup?.confirmed === true;
  const pending = personal !== null && !confirmed;
  const actionProminent = passed === false && pending;
  const link = (path: string) => withSeason(path, seasonId);

  const lineupState = !authenticated
    ? "Inicia sesión para consultar tu equipo."
    : me.loading
      ? "Consultando tu alineación…"
      : !personal
        ? "No se pudo consultar tu participación o alineación."
        : confirmed
          ? "Alineación confirmada"
          : personal.current_lineup
            ? "Alineación guardada · sin confirmar"
            : "Sin alineación registrada";

  return (
    <section className={styles.home} aria-label="Tu jornada y tus rivales">
      <header className={styles.header}>
        <h1 className={styles.title}>Jornada {displayed?.number ?? current.number}</h1>
        <p className={styles.eyebrow}>{seasonName}</p>
      </header>

      <div
        className={styles.lineup}
        data-prominent={actionProminent}
        data-lineup-state={confirmed ? "confirmed" : personal ? "pending" : "unknown"}
      >
        <div className={styles.lineupCopy}>
          <span className={styles.lineupIcon} aria-hidden="true">
            {confirmed ? "✓" : "▤"}
          </span>
          <div>
            <h2>Mi alineación · J{current.number}</h2>
            <p className={styles.lineupState}>{lineupState}</p>
            {passed === false && current.deadline_at && (
              <p className={styles.lineupHint}>
                Cierre:{" "}
                {new Date(current.deadline_at).toLocaleString("es-ES", {
                  timeZone: "Europe/Madrid",
                })}{" "}
                (Madrid)
              </p>
            )}
            {passed === null && !final && (
              <p className={styles.lineupHint}>
                Plazo sin verificar. No mostramos alineaciones rivales de esta jornada.
              </p>
            )}
          </div>
        </div>
        <Link
          href={authenticated ? link(`/jornadas/${current.number}/alineacion`) : "/login"}
          className={styles.lineupAction}
        >
          {!authenticated
            ? "Iniciar sesión"
            : passed === false && pending
              ? "Preparar mi alineación"
              : "Ver mi alineación"}
        </Link>
      </div>

      {participantId !== null && displayed && (
        <YourMatchday
          matchday={displayed}
          participantId={participantId}
          standings={standings}
          weeklyRules={weeklyRules}
          final={isMatchdayFinal(displayed)}
        />
      )}

      <div className={styles.layout} data-home-layout>
        <div className={styles.main} data-home-main>
          {participantId !== null && displayed && (
            <YourLineup
              seasonId={seasonId}
              matchdayNumber={displayed.number}
              participantId={participantId}
              refreshKey={refreshKey}
            />
          )}
          {participantId !== null && (
            <PersonalPlayoff
              seasonId={seasonId}
              matchdayNumber={playoff.number}
              participantId={participantId}
              phase={playoff.phase}
              scores={playoff.scores}
              refreshKey={refreshKey}
            />
          )}
          {displayed ? (
            <>
              <MatchdayAccordion
                key={`${seasonId}:${displayed.number}`}
                refreshKey={refreshKey}
                data={displayed}
                seasonId={seasonId}
                participantId={participantId}
                weeklyRules={weeklyRules}
              />
              <MatchdayIncidents
                seasonId={seasonId}
                matchdayNumber={displayed.number}
                enabled={true}
                refreshKey={refreshKey}
              />
            </>
          ) : (
            <p className={`${styles.card} ${styles.empty}`}>
              La comparación de esta jornada aparecerá cuando cierre el plazo de alineación.
            </p>
          )}
          <LeagueSummary
            seasonId={seasonId}
            participantId={participantId}
            matchdayNumber={displayed?.number ?? null}
            isTournament={isTournament}
            economyEnabled={economyEnabled}
            copa={copa}
            economy={economy}
            groups={groups}
          />
        </div>
        <aside
          className={styles.rail}
          aria-label="Clasificación y accesos de tu liga"
          data-home-rail
        >
          <Podium entries={standings} participantId={participantId} seasonId={seasonId} />
          <nav
            className={`${styles.card} ${styles.shortcuts}`}
            aria-label="Explorar la competición"
          >
            <h2>Más de tu liga</h2>
            <Link href={link("/jornadas")}>
              Todas las jornadas <span aria-hidden="true">↗</span>
            </Link>
            {appliesToCompetition("/copa", isTournament) && (
              <Link href={link("/copa")}>
                Seguir la Copa <span aria-hidden="true">↗</span>
              </Link>
            )}
            {economyEnabled && (
              <Link href={link("/economia")}>
                Economía de la liga <span aria-hidden="true">↗</span>
              </Link>
            )}
            <Link href={link("/ranking")}>
              Rankings de la temporada <span aria-hidden="true">↗</span>
            </Link>
          </nav>
          <p className={styles.railNote}>
            Los puntos pueden cambiar hasta que se cierre la jornada. «Pendientes» se refiere a
            estadísticas aún sin procesar, no necesariamente a partidos por jugar.
          </p>
        </aside>
      </div>
    </section>
  );
}
