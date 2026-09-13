"use client";

import {
  createContext,
  Suspense,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
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
export const SEASON_PARAM = "season";

/**
 * Which season this render is about, in order of authority.
 *
 * The URL wins. It is the only source a reader can see, share and reload, and
 * the only one that can differ between two open tabs — which is precisely the
 * case that used to leave a screen operating on a season other than the one the
 * menu named. `localStorage` only chooses where you land when the URL is silent;
 * it must never contradict an explicit address.
 */
export function resolveSeason(
  seasons: SeasonSummary[],
  fromUrl: string | null,
  fromStorage: string | null,
): SeasonSummary | null {
  const byId = (raw: string | null) => {
    if (!raw) return null;
    const id = Number(raw);
    return Number.isFinite(id) ? (seasons.find((s) => s.id === id) ?? null) : null;
  };
  const active = (kind: "league" | "tournament") =>
    seasons.find((s) => s.status === "active" && (s.kind ?? "league") === kind) ?? null;

  return (
    byId(fromUrl) ??
    byId(fromStorage) ??
    active("league") ??
    active("tournament") ??
    seasons[0] ??
    null
  );
}

/**
 * Reports `?season=` upwards, and nothing else.
 *
 * `useSearchParams` opts its whole subtree out of prerendering unless a Suspense
 * boundary stands above it — Next fails the build otherwise. Isolating the read
 * in a component that renders nothing keeps that boundary around a single null,
 * so the navigation bar and the page still prerender as before.
 */
function SeasonParam({ onChange }: { onChange: (value: string | null) => void }) {
  const value = useSearchParams().get(SEASON_PARAM);
  useEffect(() => {
    onChange(value);
  }, [value, onChange]);
  return null;
}

export function SeasonProvider({ children }: { children: React.ReactNode }) {
  const [seasons, setSeasons] = useState<SeasonSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [seasonParam, setSeasonParam] = useState<string | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    apiClient
      .get<SeasonSummary[]>("/seasons")
      .then(setSeasons)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Derived, not stored: with the URL as the source of truth there is no second
  // copy of the selection to drift out of step with the address bar.
  const selectedSeason = useMemo(
    () =>
      resolveSeason(
        seasons,
        seasonParam,
        typeof window === "undefined" ? null : localStorage.getItem(STORAGE_KEY),
      ),
    [seasons, seasonParam],
  );

  const selectSeason = useCallback(
    (id: number) => {
      if (!seasons.some((s) => s.id === id)) return;
      if (typeof window === "undefined") return;
      localStorage.setItem(STORAGE_KEY, String(id));
      // Read the query off the location rather than useSearchParams: this only
      // ever runs from a click, and keeping the hook out of the provider is what
      // lets everything above it still prerender.
      const next = new URLSearchParams(window.location.search);
      next.set(SEASON_PARAM, String(id));
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [seasons, router, pathname],
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

  // Apply tournament theme class on body when in tournament context.
  // Class drives CSS variables override + background pattern.
  useEffect(() => {
    if (typeof document === "undefined") return;
    const body = document.body;
    const TOURNAMENT_CLASSES = [
      "tournament-active",
      "tournament-mundial",
      "tournament-eurocopa",
      "tournament-copa_america",
    ];
    body.classList.remove(...TOURNAMENT_CLASSES);
    if (derived.isTournamentContext && selectedSeason?.tournament_type) {
      body.classList.add("tournament-active");
      body.classList.add(`tournament-${selectedSeason.tournament_type}`);
    }
    return () => {
      body.classList.remove(...TOURNAMENT_CLASSES);
    };
  }, [derived.isTournamentContext, selectedSeason?.tournament_type]);

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
      <Suspense fallback={null}>
        <SeasonParam onChange={setSeasonParam} />
      </Suspense>
      {children}
    </SeasonContext>
  );
}

export function useSeason() {
  return useContext(SeasonContext);
}
