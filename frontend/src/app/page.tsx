"use client";

import { useSeason } from "@/contexts/season-context";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { MatchdayAccordion } from "@/components/dashboard/matchday-accordion";
import { Podium } from "@/components/dashboard/podium";
import { NavCards } from "@/components/dashboard/nav-cards";
import { CopaWidget } from "@/components/dashboard/copa-widget";
import { CopaMatchdayWidget } from "@/components/dashboard/copa-matchday-widget";
import { SkeletonCards } from "@/components/ui/skeleton";

export default function Home() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const {
    standings,
    currentMatchdayDetail,
    copaData,
    loading,
  } = useDashboardData(
    selectedSeason?.id ?? null,
    selectedSeason?.matchday_current ?? null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 animate-pulse rounded bg-vpv-border" />
        <SkeletonCards count={3} />
      </div>
    );
  }

  const leader = standings?.entries[0] ?? null;
  const copaLeader = copaData?.standings[0] ?? null;
  const currentCopaMatchday = copaData?.matchdays.find(
    (md) => md.matchday_number === selectedSeason?.matchday_current,
  ) ?? null;

  const navCards = [
    {
      title: "Liga",
      href: "/clasificacion",
      icon: "trophy" as const,
      detail: leader
        ? `Lider: ${leader.display_name} (${leader.total_points} pts)`
        : "Tabla general",
    },
    {
      title: "Copa",
      href: "/copa",
      icon: "shield" as const,
      detail: copaLeader
        ? `Lider: ${copaLeader.display_name} (${copaLeader.total_points} pts)`
        : "Competicion Copa",
    },
    {
      title: "Jornadas",
      href: "/jornadas",
      icon: "calendar" as const,
      detail: currentMatchdayDetail
        ? `Actual: J${currentMatchdayDetail.number}`
        : "Puntuaciones por jornada",
    },
    {
      title: "Plantillas",
      href: "/plantillas",
      icon: "users" as const,
      detail: `${selectedSeason?.total_participants ?? 0} participantes`,
    },
    {
      title: "Drafts",
      href: "/drafts",
      icon: "shuffle" as const,
      detail: "Historial de elecciones",
    },
    {
      title: "Economia",
      href: "/economia",
      icon: "coins" as const,
      detail: "Balance global de pagos",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-vpv-text">Liga VPV</h1>
        {selectedSeason && (
          <p className="mt-1 text-vpv-text-muted">
            Temporada {selectedSeason.name}
          </p>
        )}
      </div>

      {currentMatchdayDetail && selectedSeason && (
        <MatchdayAccordion
          data={currentMatchdayDetail}
          seasonId={selectedSeason.id}
        />
      )}

      {standings && standings.entries.length > 0 && (
        <Podium entries={standings.entries} />
      )}

      {currentCopaMatchday && (
        <CopaMatchdayWidget matchday={currentCopaMatchday} />
      )}

      {copaData && copaData.standings.length > 0 && (
        <CopaWidget entries={copaData.standings} />
      )}

      <NavCards cards={navCards} />
    </div>
  );
}
