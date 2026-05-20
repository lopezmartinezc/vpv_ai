"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SkeletonCards } from "@/components/ui/skeleton";
import { TournamentHero } from "@/components/tournament/tournament-hero";
import type { TournamentGroupsResponse } from "@/types";

export default function GruposPage() {
  const { selectedSeason, loading: seasonLoading, isTournamentContext } =
    useSeason();

  if (!seasonLoading && !isTournamentContext) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">
          Esta vista solo aplica a torneos con fase de grupos.
        </p>
      </div>
    );
  }

  return <GruposContent />;
}

function GruposContent() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading, error } = useFetch<TournamentGroupsResponse>(
    selectedSeason ? `/tournaments/${selectedSeason.id}/groups` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 animate-pulse rounded bg-vpv-border" />
        <SkeletonCards count={4} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">No se pudieron cargar los grupos</p>
      </div>
    );
  }

  if (data.groups.length === 0) {
    return (
      <div className="space-y-6">
        <TournamentHero
          title="Fase de grupos"
          subtitle="Clasificacion de los 8 grupos"
          mascot="maple"
        />
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
          <p className="text-vpv-text-muted">
            Aun no hay equipos asignados a grupos. Configura los grupos
            desde el admin antes del torneo.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <TournamentHero
        title="Fase de grupos"
        subtitle="Clasificacion de los 8 grupos"
        mascot="maple"
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {data.groups.map((group) => (
          <GroupCard key={group.name} group={group} />
        ))}
      </div>
    </div>
  );
}

function GroupCard({
  group,
}: {
  group: TournamentGroupsResponse["groups"][number];
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-border bg-vpv-bg/50 px-4 py-2">
        <h2 className="font-semibold text-vpv-text">Grupo {group.name}</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border text-xs text-vpv-text-muted">
              <th className="px-3 py-2 text-left">Equipo</th>
              <th className="px-1 py-2 text-center">PJ</th>
              <th className="px-1 py-2 text-center">G</th>
              <th className="px-1 py-2 text-center">E</th>
              <th className="px-1 py-2 text-center">P</th>
              <th className="px-1 py-2 text-center">GF</th>
              <th className="px-1 py-2 text-center">GC</th>
              <th className="px-1 py-2 text-center">DG</th>
              <th className="px-3 py-2 text-right font-semibold">Pts</th>
            </tr>
          </thead>
          <tbody>
            {group.teams.map((t, idx) => {
              const qualifies = idx < 2;
              return (
                <tr
                  key={t.team_id}
                  className={`border-b border-vpv-border last:border-0 ${
                    qualifies ? "bg-green-500/5" : ""
                  }`}
                >
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      {t.logo_path && (
                        <img
                          src={t.logo_path}
                          alt=""
                          className="h-5 w-5"
                        />
                      )}
                      <span className="font-medium text-vpv-text">
                        {t.short_name ?? t.team_name}
                      </span>
                    </div>
                  </td>
                  <td className="px-1 py-2 text-center tabular-nums text-vpv-text-muted">
                    {t.played}
                  </td>
                  <td className="px-1 py-2 text-center tabular-nums text-vpv-text-muted">
                    {t.won}
                  </td>
                  <td className="px-1 py-2 text-center tabular-nums text-vpv-text-muted">
                    {t.drawn}
                  </td>
                  <td className="px-1 py-2 text-center tabular-nums text-vpv-text-muted">
                    {t.lost}
                  </td>
                  <td className="px-1 py-2 text-center tabular-nums text-vpv-text-muted">
                    {t.goals_for}
                  </td>
                  <td className="px-1 py-2 text-center tabular-nums text-vpv-text-muted">
                    {t.goals_against}
                  </td>
                  <td className="px-1 py-2 text-center tabular-nums text-vpv-text-muted">
                    {t.goal_diff > 0 ? `+${t.goal_diff}` : t.goal_diff}
                  </td>
                  <td className="px-3 py-2 text-right font-bold tabular-nums text-vpv-text">
                    {t.points}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
