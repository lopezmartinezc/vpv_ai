"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { apiClient } from "@/lib/api-client";
import type { SeasonSummary } from "@/types";

interface SeasonContextValue {
  seasons: SeasonSummary[];
  selectedSeason: SeasonSummary | null;
  selectSeason: (id: number) => void;
  loading: boolean;
}

const SeasonContext = createContext<SeasonContextValue>({
  seasons: [],
  selectedSeason: null,
  selectSeason: () => {},
  loading: true,
});

export function SeasonProvider({ children }: { children: React.ReactNode }) {
  const [seasons, setSeasons] = useState<SeasonSummary[]>([]);
  const [selectedSeason, setSelectedSeason] = useState<SeasonSummary | null>(
    null,
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get<SeasonSummary[]>("/seasons")
      .then((data) => {
        setSeasons(data);
        const active = data.find((s) => s.status === "active") ?? data[0];
        if (active) setSelectedSeason(active);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const selectSeason = useCallback(
    (id: number) => {
      const season = seasons.find((s) => s.id === id);
      if (season) setSelectedSeason(season);
    },
    [seasons],
  );

  return (
    <SeasonContext value={{ seasons, selectedSeason, selectSeason, loading }}>
      {children}
    </SeasonContext>
  );
}

export function useSeason() {
  return useContext(SeasonContext);
}
