"use client";

import { useCallback, useMemo } from "react";
import { useSeason } from "@/contexts/season-context";
import { useAuth } from "@/contexts/auth-context";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { useFetch } from "@/hooks/use-fetch";
import { appliesToCompetition } from "@/lib/competition-scope";
import { weeklyRulesFrom, type SeasonPaymentEntry } from "@/lib/weekly-payments";
import { CompetitiveHome } from "@/components/dashboard/competitive-home";
import { LeagueSummary } from "@/components/dashboard/league-summary";
import { UnavailableNotice } from "@/components/dashboard/unavailable-notice";
import { Podium } from "@/components/dashboard/podium";
import { NavCards } from "@/components/dashboard/nav-cards";
import { TournamentHero } from "@/components/tournament/tournament-hero";
import { SkeletonCards } from "@/components/ui/skeleton";
import { Logo } from "@/components/ui/logo";
import type { GroupStandingsResponse, MatchdayDetailResponse } from "@/types";

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

  const weeklyRules = useMemo(() => weeklyRulesFrom(payments ?? []), [payments]);

  const refreshDashboard = useCallback(() => {
    refetch();
    refreshPrevious();
  }, [refetch, refreshPrevious]);

  if (seasonLoading || loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 animate-pulse rounded bg-vpv-border" />
        <SkeletonCards count={3} />
      </div>
    );
  }

  // Hide every Pagometro/Economia surface for seasons without the
  // weekly-payments mechanic (typical for Mundial / torneos cortos).
  // `undefined` is treated as enabled so older API bundles keep their
  // behavior; the gate fires only on an explicit `false`.
  const economyEnabled = selectedSeason?.weekly_payments_enabled !== false;

  // The Copa is a league competition: the same rule as the menu (IN-04).
  const copaApplies = appliesToCompetition("/copa", isTournamentContext);
  const leader = standings?.entries[0] ?? null;
  const copaLeader = copaApplies ? (copaData?.standings[0] ?? null) : null;

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
          weeklyRules={economyEnabled ? weeklyRules : undefined}
          copa={copaData}
          economy={economy}
          groups={groupStandings}
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

      {selectedSeason && !currentMatchdayDetail && (
        <>
          <LeagueSummary
            seasonId={selectedSeason.id}
            participantId={null}
            matchdayNumber={null}
            isTournament={isTournamentContext}
            economyEnabled={economyEnabled}
            copa={copaData}
            economy={economy}
            groups={groupStandings}
          />
          <NavCards cards={navCards} />
        </>
      )}
    </div>
  );
}
