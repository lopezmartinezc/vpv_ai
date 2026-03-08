"use client";

import { useMemo } from "react";
import { useSeason } from "@/contexts/season-context";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { useFetch } from "@/hooks/use-fetch";
import { MatchdayAccordion } from "@/components/dashboard/matchday-accordion";
import { Podium } from "@/components/dashboard/podium";
import { NavCards } from "@/components/dashboard/nav-cards";
import { CopaWidget } from "@/components/dashboard/copa-widget";
import { CopaMatchdayWidget } from "@/components/dashboard/copa-matchday-widget";
import { PagometroJornadaWidget } from "@/components/dashboard/pagometro-jornada-widget";
import { PagometroWidget } from "@/components/dashboard/pagometro-widget";
import { SkeletonCards } from "@/components/ui/skeleton";
import { Logo } from "@/components/ui/logo";

interface SeasonPaymentEntry {
  id: number;
  payment_type: string;
  position_rank: number | null;
  amount: number;
  description: string | null;
}

export default function Home() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const {
    standings,
    currentMatchdayDetail,
    copaData,
    economy,
    loading,
  } = useDashboardData(
    selectedSeason?.id ?? null,
    selectedSeason?.matchday_current ?? null,
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
      title: "Economia",
      href: "/economia",
      icon: "coins" as const,
      detail: "Balance global de pagos",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Logo className="h-16 w-auto text-vpv-accent" />
        {selectedSeason && (
          <p className="text-sm text-vpv-text-muted">
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

      {currentMatchdayDetail &&
        currentMatchdayDetail.stats_ok &&
        currentMatchdayDetail.scores.length > 0 &&
        Object.keys(weeklyRules).length > 0 && (
          <PagometroJornadaWidget
            scores={currentMatchdayDetail.scores}
            matchdayNumber={currentMatchdayDetail.number}
            weeklyRules={weeklyRules}
          />
        )}

      {economy && economy.balances.length > 0 && (
        <PagometroWidget balances={economy.balances} />
      )}

      <NavCards cards={navCards} />
    </div>
  );
}
