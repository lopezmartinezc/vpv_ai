"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { apiClient } from "@/lib/api-client";
import type { SeasonSummary } from "@/types";

interface SeasonContextValue {
  seasons: SeasonSummary[];
  selectedSeason: SeasonSummary | null;
  selectSeason: (id: number) => void;
  loading: boolean;
  /** All currently active seasons (status='active'). */
  activeSeasons: SeasonSummary[];
  /** Active Liga (kind='league') if any. */
  activeLeague: SeasonSummary | null;
  /** Active Tournament (kind='tournament') if any. */
  activeTournament: SeasonSummary | null;
  /** Whether the selected season is a tournament. Drives menu adaptation. */
  isTournamentContext: boolean;
}

const SeasonContext = createContext<SeasonContextValue>({
  seasons: [],
  selectedSeason: null,
  selectSeason: () => {},
  loading: true,
  activeSeasons: [],
  activeLeague: null,
  activeTournament: null,
  isTournamentContext: false,
});

const STORAGE_KEY = "vpv_selected_season_id";

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

        // Restore previous selection if still valid
        let initial: SeasonSummary | null = null;
        if (typeof window !== "undefined") {
          const stored = localStorage.getItem(STORAGE_KEY);
          if (stored) {
            const storedId = Number(stored);
            initial = data.find((s) => s.id === storedId) ?? null;
          }
        }

        // Fallback: prefer active Liga, then active tournament, then most recent
        if (initial == null) {
          const activeLeague = data.find(
            (s) => s.status === "active" && (s.kind ?? "league") === "league",
          );
          const activeTournament = data.find(
            (s) => s.status === "active" && s.kind === "tournament",
          );
          initial = activeLeague ?? activeTournament ?? data[0] ?? null;
        }

        if (initial) setSelectedSeason(initial);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const selectSeason = useCallback(
    (id: number) => {
      const season = seasons.find((s) => s.id === id);
      if (season) {
        setSelectedSeason(season);
        if (typeof window !== "undefined") {
          localStorage.setItem(STORAGE_KEY, String(id));
        }
      }
    },
    [seasons],
  );

  const derived = useMemo(() => {
    const activeSeasons = seasons.filter((s) => s.status === "active");
    const activeLeague =
      activeSeasons.find((s) => (s.kind ?? "league") === "league") ?? null;
    const activeTournament =
      activeSeasons.find((s) => s.kind === "tournament") ?? null;
    const isTournamentContext = selectedSeason?.kind === "tournament";
    return { activeSeasons, activeLeague, activeTournament, isTournamentContext };
  }, [seasons, selectedSeason]);

  return (
    <SeasonContext
      value={{
        seasons,
        selectedSeason,
        selectSeason,
        loading,
        ...derived,
      }}
    >
      {children}
    </SeasonContext>
  );
}

export function useSeason() {
  return useContext(SeasonContext);
}
