"use client";

import { useSeason } from "@/contexts/season-context";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { MatchdayAccordion } from "@/components/dashboard/matchday-accordion";
import { Podium } from "@/components/dashboard/podium";
import { QuickStats } from "@/components/dashboard/quick-stats";
import { NavCards } from "@/components/dashboard/nav-cards";
import { SkeletonCards } from "@/components/ui/skeleton";

export default function Home() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const {
    standings,
    currentMatchdayDetail,
    totalPlayed,
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

  const navCards = [
    {
      title: "Clasificacion",
      href: "/clasificacion",
      icon: "trophy" as const,
      detail: leader
        ? `Lider: ${leader.display_name} (${leader.total_points} pts)`
        : "Tabla general",
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
        <h1 className="text-2xl font-bold text-vpv-text">Liga VPV Fantasy</h1>
        {selectedSeason && (
          <p className="mt-1 text-vpv-text-muted">
            Temporada {selectedSeason.name} &mdash;{" "}
            {selectedSeason.total_participants} participantes
          </p>
        )}
      </div>

      {currentMatchdayDetail && selectedSeason && (
        <MatchdayAccordion
          data={currentMatchdayDetail}
          seasonId={selectedSeason.id}
        />
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {standings && standings.entries.length > 0 && (
          <Podium entries={standings.entries} />
        )}

        <QuickStats
          totalPlayed={totalPlayed}
          totalParticipants={selectedSeason?.total_participants ?? 0}
          leaderName={leader?.display_name ?? null}
          leaderPoints={leader?.total_points ?? null}
        />
      </div>

      <NavCards cards={navCards} />
    </div>
  );
}
