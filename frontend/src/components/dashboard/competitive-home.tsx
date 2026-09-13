"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useFetch } from "@/hooks/use-fetch";
import { appliesToCompetition } from "@/lib/competition-scope";
import { isMatchdayFinal } from "@/lib/matchday-status";
import { withSeason } from "@/lib/season-link";
import type { MatchdayDetailResponse, MyLineupResponse, StandingEntry } from "@/types";
import { MatchdayAccordion } from "./matchday-accordion";
import { MatchdayIncidents } from "./matchday-incidents";
import { PersonalPlayoff } from "./personal-playoff";
import { Podium } from "./podium";
import styles from "./home.module.css";

interface DeadlineStatus {
  has_lineup: boolean;
  deadline_at: string | null;
  minutes_remaining: number | null;
  matchday_number: number;
}

// Only the server's effective deadline is used, including explicit overrides.
export function isDeadlinePassed(
  status: DeadlineStatus | null,
  matchday: number,
  now: number,
): boolean | null {
  if (!status || status.matchday_number !== matchday || !status.deadline_at) return null;
  const time = Date.parse(status.deadline_at);
  return Number.isFinite(time) ? now >= time : null;
}

export function CompetitiveHome({
  seasonId,
  seasonName = "Liga VPV",
  economyEnabled = false,
  isTournament = false,
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
  current: MatchdayDetailResponse;
  previous: MatchdayDetailResponse | null;
  authenticated: boolean;
  standings: StandingEntry[];
  onRefresh: () => void;
}) {
  const me = useFetch<MyLineupResponse>(
    authenticated ? `/lineups/${seasonId}/${current.number}/me` : null,
  );
  const deadline = useFetch<DeadlineStatus>(
    authenticated ? `/lineups/${seasonId}/deadline-status` : null,
  );
  const [refreshKey, setRefreshKey] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const refreshMe = me.refetch;
  const refreshDeadline = deadline.refetch;
  const refresh = useCallback(() => {
    refreshMe();
    refreshDeadline();
    onRefresh();
    setRefreshKey((value) => value + 1);
    setUpdatedAt(new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }));
  }, [refreshMe, refreshDeadline, onRefresh]);
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
    () => isDeadlinePassed(authenticated ? deadline.data : null, current.number, Date.now()),
    () => null,
  );
  const final = isMatchdayFinal(current);
  const showCurrent = passed === true || final;
  const displayed = showCurrent
    ? current
    : previous && isMatchdayFinal(previous)
      ? previous
      : null;
  const personal = authenticated ? me.data : null;
  const participantId = personal?.participant_id ?? null;
  const position = standings.find((entry) => entry.participant_id === participantId);
  const confirmed = personal?.current_lineup?.confirmed === true;
  const pending = personal !== null && !confirmed;
  const actionProminent = passed === false && pending;
  const link = (path: string) => withSeason(path, seasonId);

  const personalScore = displayed?.scores.find((entry) => entry.participant_id === participantId);
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
        <div>
          <p className={styles.eyebrow}>
            {seasonName} <span aria-hidden="true"> / </span> Jornada {current.number}
          </p>
          <h1 className={styles.title}>Tu liga. Tu jornada.</h1>
          <p className={styles.subtitle}>
            Cada punto cuenta. Sigue tu once y no pierdas de vista a tus rivales.
          </p>
        </div>
        <div className={styles.refresh}>
          <button type="button" onClick={refresh}>
            <span aria-hidden="true">↻</span> Actualizar jornada
          </button>
          <small>Consulta cada minuto{updatedAt ? ` · solicitada a las ${updatedAt}` : ""}</small>
        </div>
      </header>

      <dl className={styles.metrics} aria-label="Tu resumen competitivo">
        <div className={styles.metric}>
          <dt>Tus puntos{displayed ? ` · J${displayed.number}` : " de jornada"}</dt>
          <dd>
            {personalScore?.total_points ?? "—"}
            <small>pts</small>
          </dd>
        </div>
        <div className={styles.metric}>
          <dt>Posición general</dt>
          <dd>
            {position ? `${position.rank}.º` : "—"}
            <small>{position ? `de ${standings.length}` : "sin datos"}</small>
          </dd>
        </div>
        <div className={styles.metric}>
          <dt>Pendientes de puntuar{displayed ? ` · J${displayed.number}` : ""}</dt>
          <dd>
            {personalScore?.pending_players ?? "—"}
            <small>jugadores</small>
          </dd>
        </div>
      </dl>

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
            {passed === false && deadline.data?.deadline_at && (
              <p className={styles.lineupHint}>
                Cierre:{" "}
                {new Date(deadline.data.deadline_at).toLocaleString("es-ES", {
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

      <div className={styles.layout} data-home-layout>
        <div className={styles.main} data-home-main>
          {participantId !== null && (
            <PersonalPlayoff
              seasonId={seasonId}
              matchdayNumber={current.number}
              participantId={participantId}
              scores={showCurrent ? current.scores : undefined}
              refreshKey={refreshKey}
              matchdayFinal={final}
            />
          )}
          {displayed ? (
            <>
              {!showCurrent && (
                <p className={styles.previous}>
                  Últimos resultados disponibles · J{displayed.number}. La próxima jornada es J
                  {current.number}.
                </p>
              )}
              <MatchdayAccordion
                key={`${seasonId}:${displayed.number}`}
                refreshKey={refreshKey}
                data={displayed}
                seasonId={seasonId}
                participantId={participantId}
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
              La comparación de esta jornada aparecerá cuando se verifique el cierre. Todavía no hay
              resultados anteriores disponibles.
            </p>
          )}
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
