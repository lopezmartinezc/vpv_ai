"use client";

import { useFetch } from "./use-fetch";
import type { DashboardResponse } from "@/types";

export function useDashboardData(
  seasonId: number | null,
  matchdayCurrent: number | null,
) {
  const path =
    seasonId != null
      ? `/dashboard/${seasonId}${matchdayCurrent != null ? `?matchday_current=${matchdayCurrent}` : ""}`
      : null;

  const { data, loading } = useFetch<DashboardResponse>(path);

  return {
    standings: data?.standings ?? null,
    currentMatchdayDetail: data?.current_matchday ?? null,
    copaData: data?.copa ?? null,
    economy: data?.economy ?? null,
    loading,
  };
}
