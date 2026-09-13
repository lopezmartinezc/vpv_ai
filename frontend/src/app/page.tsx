"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";
import { useSeason } from "@/contexts/season-context";
import { useAuth } from "@/contexts/auth-context";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { useFetch } from "@/hooks/use-fetch";
import { appliesToCompetition } from "@/lib/competition-scope";
import { CompetitiveHome } from "@/components/dashboard/competitive-home";
import { UnavailableNotice } from "@/components/dashboard/unavailable-notice";
import { Podium } from "@/components/dashboard/podium";
import { NavCards } from "@/components/dashboard/nav-cards";
import { CopaWidget } from "@/components/dashboard/copa-widget";
import { CopaMatchdayWidget } from "@/components/dashboard/copa-matchday-widget";
import { PagometroJornadaWidget } from "@/components/dashboard/pagometro-jornada-widget";
import { PagometroWidget } from "@/components/dashboard/pagometro-widget";
import { TournamentHero } from "@/components/tournament/tournament-hero";
import { SkeletonCards } from "@/components/ui/skeleton";
import homeStyles from "@/components/dashboard/home.module.css";
import { Logo } from "@/components/ui/logo";
import type { GroupStandingsResponse, MatchdayDetailResponse } from "@/types";

interface SeasonPaymentEntry {
  id: number;
  payment_type: string;
  position_rank: number | null;
  amount: number;
  description: string | null;
}

export default function Home() {
  const { user } = useAuth();
  const { selectedSeason, loading: seasonLoading, isTournamentContext } = useSeason();
  const mdCurrent = selectedSeason?.matchday_current ?? null;
  const {
    standings,
    currentMatchdayDetail,
    copaData,
    economy,
    loading,
    error,
    refetch,
    unavailable,
  } = useDashboardData(selectedSeason?.id ?? null, mdCurrent);

  const { data: groupStandings } = useFetch<GroupStandingsResponse>(
    selectedSeason ? `/standings/${selectedSeason.id}/groups` : null,
  );

  // Fetch previous matchday to show when current has no scores yet
  const prevNumber = mdCurrent && mdCurrent > 1 ? mdCurrent - 1 : null;
  const { data: prevMatchday, refetch: refreshPrevious } = useFetch<MatchdayDetailResponse>(
    selectedSeason && prevNumber ? `/matchdays/${selectedSeason.id}/${prevNumber}` : null,
  );

  const { data: payments } = useFetch<SeasonPaymentEntry[]>(
    selectedSeason ? `/seasons/${selectedSeason.id}/payments` : null,
  );

  const weeklyRules = useMemo(() => {
    if (!payments) return {};
    const rules: Record<number, number> = {};
    for (const p of payments) {
      if (p.payment_type === "weekly_position" && p.position_rank !== null) {
        rules[p.position_rank] = p.amount;
      }
    }
    return rules;
  }, [payments]);

  const refreshDashboard = useCallback(() => {
    refetch();
    refreshPrevious();
  }, [refetch, refreshPrevious]);

  // Which matchday the Copa and Pagometro widgets follow (re-checked every 30s).
  // The lineup and the rivals follow the server's deadline, in CompetitiveHome.
  const firstMatchAt = currentMatchdayDetail?.first_match_at ?? null;
  const dlMin = selectedSeason?.lineup_deadline_min ?? 0;
  const subscribe = useCallback((cb: () => void) => {
    const id = setInterval(cb, 30_000);
    return () => clearInterval(id);
  }, []);
  const deadlinePassed = useSyncExternalStore(
    subscribe,
    () => {
      if (!firstMatchAt) return true;
      const deadlineMs = new Date(firstMatchAt).getTime() - dlMin * 60_000;
      return Date.now() >= deadlineMs;
    },
    () => true,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 animate-pulse rounded bg-vpv-border" />
        <SkeletonCards count={3} />
      </div>
    );
  }

  // Show previous matchday until deadline passes, then show current
  const displayMatchday = deadlinePassed
    ? currentMatchdayDetail
    : (prevMatchday ?? currentMatchdayDetail);

  // Pagometro uses whichever matchday is being displayed
  const pagometroMatchday = displayMatchday?.stats_ok ? displayMatchday : null;

  // Hide every Pagometro/Economia surface for seasons without the
  // weekly-payments mechanic (typical for Mundial / torneos cortos).
  // `undefined` is treated as enabled so older API bundles keep their
  // behavior; the gate fires only on an explicit `false`.
  const economyEnabled = selectedSeason?.weekly_payments_enabled !== false;

  // The Copa is a league competition: the same rule as the menu (IN-04).
  const copaApplies = appliesToCompetition("/copa", isTournamentContext);
  const copaStandings = copaApplies ? (copaData?.standings ?? []) : [];
  const currentCopaMatchday = copaApplies
    ? (copaData?.matchdays.find(
        (md) => md.matchday_number === (displayMatchday?.number ?? mdCurrent),
      ) ?? null)
    : null;

  const leader = standings?.entries[0] ?? null;
  const copaLeader = copaStandings[0] ?? null;

  const navCards = [
    {
      title: "Liga",
      href: "/clasificacion",
      icon: "trophy" as const,
      detail: leader
        ? `Lider: ${leader.display_name} (${leader.total_points} pts)`
        : "Tabla general",
    },
    ...(copaApplies
      ? [
          {
            title: "Copa",
            href: "/copa",
            icon: "shield" as const,
            detail: copaLeader
              ? `Lider: ${copaLeader.display_name} (${copaLeader.total_points} pts)`
              : "Competicion Copa",
          },
        ]
      : []),
    {
      title: "Jornadas",
      href: "/jornadas",
      icon: "calendar" as const,
      detail: currentMatchdayDetail
        ? `Actual: J${currentMatchdayDetail.number}`
        : "Puntuaciones por jornada",
    },
    ...(economyEnabled
      ? [
          {
            title: "Economia",
            href: "/economia",
            icon: "coins" as const,
            detail: "Balance global de pagos",
          },
        ]
      : []),
  ];

  const hasSecondary = Boolean(
    currentCopaMatchday ||
    copaStandings.length ||
    groupStandings?.groups.length ||
    (economyEnabled &&
      (economy?.balances.length ||
        (pagometroMatchday?.scores.length && Object.keys(weeklyRules).length))),
  );

  return (
    <div className="space-y-6">
      {!currentMatchdayDetail && (
        <TournamentHero
          title="Inicio"
          subtitle="Bienvenido al fantasy del Mundial"
          onlyInTournamentContext
        />
      )}
      {!isTournamentContext && !currentMatchdayDetail && (
        <div className="flex items-center gap-4">
          <Logo className="h-16 w-auto text-vpv-accent" />
          {selectedSeason && (
            <p className="text-sm text-vpv-text-muted">Temporada {selectedSeason.name}</p>
          )}
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-vpv-danger p-4 text-sm text-vpv-text">
          No se pudo cargar el Inicio.{" "}
          <button type="button" onClick={refetch} className="min-h-11 text-vpv-accent">
            Reintentar
          </button>
        </div>
      )}
      <UnavailableNotice sections={unavailable} onRetry={refetch} />
      {!selectedSeason && (
        <p className="text-vpv-text-muted">Selecciona una temporada para seguir tu liga.</p>
      )}
      {selectedSeason && currentMatchdayDetail && (
        <CompetitiveHome
          key={`${selectedSeason.id}:${user?.id ?? "guest"}:${currentMatchdayDetail.number}`}
          seasonId={selectedSeason.id}
          seasonName={selectedSeason.name}
          economyEnabled={economyEnabled}
          isTournament={isTournamentContext}
          current={currentMatchdayDetail}
          previous={prevMatchday}
          authenticated={user !== null}
          standings={standings?.entries ?? []}
          onRefresh={refreshDashboard}
        />
      )}
      {selectedSeason &&
        !currentMatchdayDetail &&
        !error &&
        !unavailable.includes("current_matchday") && (
          <p className="rounded-lg border border-vpv-card-border p-4 text-vpv-text-muted">
            No hay información de la jornada disponible.{" "}
            <button type="button" onClick={refetch} className="min-h-11 text-vpv-accent">
              Volver a consultar
            </button>
          </p>
        )}

      {!currentMatchdayDetail && standings && standings.entries.length > 0 && (
        <Podium entries={standings.entries} seasonId={selectedSeason?.id} />
      )}

      {(hasSecondary || !currentMatchdayDetail) && (
        <section className={homeStyles.secondary} aria-label="Más competiciones y gestión">
          <h2 className={homeStyles.secondaryTitle}>El resto de tu liga</h2>
          <div className={homeStyles.secondaryGrid}>
            {currentCopaMatchday && <CopaMatchdayWidget matchday={currentCopaMatchday} />}

            {copaStandings.length > 0 && <CopaWidget entries={copaStandings} />}

            {economyEnabled &&
              pagometroMatchday &&
              pagometroMatchday.scores.length > 0 &&
              Object.keys(weeklyRules).length > 0 && (
                <PagometroJornadaWidget
                  scores={pagometroMatchday.scores}
                  matchdayNumber={pagometroMatchday.number}
                  weeklyRules={weeklyRules}
                />
              )}

            {economyEnabled && economy && economy.balances.length > 0 && (
              <PagometroWidget balances={economy.balances} />
            )}

            {/* Group standings */}
            {groupStandings && groupStandings.groups.length > 0 && (
              <div className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden">
                <div className="border-b border-vpv-border bg-vpv-bg px-4 py-2.5">
                  <h2 className="text-sm font-semibold text-vpv-text">Grupos</h2>
                </div>
                <div className="divide-y divide-vpv-border">
                  {groupStandings.groups.map((g) => {
                    const isLast = g.rank === groupStandings.groups.length;
                    return (
                      <div
                        key={g.group_name}
                        className={`flex items-center justify-between px-4 py-2.5 ${
                          isLast ? "bg-red-500/5" : g.rank === 1 ? "bg-amber-400/5" : ""
                        }`}
                      >
                        <span className="text-sm font-medium text-vpv-text">
                          {g.rank === 1 && "🏆 "}
                          {isLast && "🍕 "}
                          {g.rank}. {g.group_name}
                        </span>
                        <span className="text-sm tabular-nums font-bold text-vpv-text">
                          {g.avg_points}{" "}
                          <span className="text-xs font-normal text-vpv-text-muted">pts/usr</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          {!currentMatchdayDetail && (
            <div className="mt-5">
              <NavCards cards={navCards} />
            </div>
          )}
        </section>
      )}
    </div>
  );
}
