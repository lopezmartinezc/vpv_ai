"use client";

import { useFetch } from "./use-fetch";
import type {
  StandingsResponse,
  MatchdayListResponse,
  MatchdayDetailResponse,
  CopaFullResponse,
} from "@/types";

export function useDashboardData(
  seasonId: number | null,
  matchdayCurrent: number | null,
) {
  const { data: standings, loading: standingsLoading } =
    useFetch<StandingsResponse>(
      seasonId ? `/standings/${seasonId}` : null,
    );

  const { data: matchdays, loading: matchdaysLoading } =
    useFetch<MatchdayListResponse>(
      seasonId ? `/matchdays/${seasonId}` : null,
    );

  const { data: currentMatchdayDetail } = useFetch<MatchdayDetailResponse>(
    seasonId && matchdayCurrent
      ? `/matchdays/${seasonId}/${matchdayCurrent}`
      : null,
  );

  const { data: copaData } = useFetch<CopaFullResponse>(
    seasonId ? `/copa/${seasonId}` : null,
  );

  const totalPlayed = matchdays?.matchdays.filter(
    (md) => md.stats_ok && md.counts,
  ).length ?? 0;

  return {
    standings,
    matchdays,
    currentMatchdayDetail,
    copaData,
    totalPlayed,
    loading: standingsLoading || matchdaysLoading,
  };
}
