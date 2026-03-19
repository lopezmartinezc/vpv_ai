"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { StandingsList } from "@/components/standings/standings-list";
import { LigaMatchdayDetail } from "@/components/standings/liga-matchday-detail";
import { EvolutionChart } from "@/components/standings/evolution-chart";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Logo } from "@/components/ui/logo";
import type {
  GroupStandingsResponse,
  MatchdayListResponse,
  StandingsResponse,
} from "@/types";

interface EvolutionEntry {
  matchday_number: number;
  participant_id: number;
  display_name: string;
  points: number;
  cumulative: number;
}

interface EvolutionResponse {
  season_id: number;
  entries: EvolutionEntry[];
}

export default function ClasificacionPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data: standings, loading: standingsLoading } =
    useFetch<StandingsResponse>(
      selectedSeason ? `/standings/${selectedSeason.id}` : null,
    );
  const { data: matchdayList, loading: matchdaysLoading } =
    useFetch<MatchdayListResponse>(
      selectedSeason ? `/matchdays/${selectedSeason.id}` : null,
    );
  const { data: evolution } = useFetch<EvolutionResponse>(
    selectedSeason ? `/standings/${selectedSeason.id}/evolution` : null,
  );
  const { data: groupStandings } = useFetch<GroupStandingsResponse>(
    selectedSeason ? `/standings/${selectedSeason.id}/groups` : null,
  );

  if (seasonLoading || standingsLoading || matchdaysLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={8} />
      </div>
    );
  }

  if (!standings) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        No se pudo cargar la clasificacion.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Logo className="h-16 w-auto text-vpv-accent" />
        <p className="text-sm text-vpv-text-muted">
          Temporada {standings.season_name}
        </p>
      </div>

      <StandingsList entries={standings.entries} />

      {/* Group standings */}
      {groupStandings && groupStandings.groups.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-vpv-text">
            Clasificacion por grupos
          </h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {groupStandings.groups.map((g) => {
              const isLast = g.rank === groupStandings.groups.length;
              return (
                <div
                  key={g.group_name}
                  className={`rounded-lg border overflow-hidden ${
                    isLast
                      ? "border-red-500/30 bg-red-500/5"
                      : g.rank === 1
                        ? "border-amber-400/30 bg-amber-400/5"
                        : "border-vpv-card-border bg-vpv-card"
                  }`}
                >
                  <div
                    className={`flex items-center justify-between px-4 py-2.5 ${
                      isLast
                        ? "bg-red-500/10"
                        : g.rank === 1
                          ? "bg-amber-400/10"
                          : "bg-vpv-bg"
                    }`}
                  >
                    <span className="text-sm font-bold text-vpv-text">
                      {g.rank === 1 && "\uD83C\uDFC6 "}
                      {g.group_name}
                      {isLast && " \uD83C\uDF55"}
                    </span>
                    <span className="text-sm font-bold tabular-nums text-vpv-text">
                      {g.total_points.toLocaleString()} pts
                    </span>
                  </div>
                  <div className="px-4 py-2 space-y-1">
                    {g.members.map((m) => (
                      <div
                        key={m.participant_id}
                        className="flex items-center justify-between text-xs"
                      >
                        <span className="text-vpv-text-muted">{m.display_name}</span>
                        <span className="tabular-nums text-vpv-text-muted">
                          {m.total_points.toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {evolution && evolution.entries.length > 0 && (
        <EvolutionChart entries={evolution.entries} />
      )}

      {selectedSeason && matchdayList && matchdayList.matchdays.length > 0 && (
        <LigaMatchdayDetail
          seasonId={selectedSeason.id}
          matchdays={matchdayList.matchdays}
          matchdayCurrent={selectedSeason.matchday_current}
        />
      )}
    </div>
  );
}
