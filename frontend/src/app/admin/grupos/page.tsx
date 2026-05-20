"use client";

import { useEffect, useMemo, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient } from "@/lib/api-client";

interface TeamOption {
  id: number;
  name: string;
  short_name: string | null;
  logo_path: string | null;
  tournament_group: string | null;
}

interface TournamentConfig {
  groups?: { count?: number; teams_per_group?: number };
}

const GROUP_LETTERS = "ABCDEFGHIJKL".split(""); // up to 12 groups

export default function AdminGruposPage() {
  const { selectedSeason, isTournamentContext, loading: seasonLoading } = useSeason();

  if (!seasonLoading && !isTournamentContext) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">
          Esta vista solo aplica a torneos. Selecciona una temporada de tipo
          torneo en el selector superior.
        </p>
      </div>
    );
  }

  return <GruposAdminContent />;
}

function GruposAdminContent() {
  const { selectedSeason } = useSeason();
  const seasonId = selectedSeason?.id ?? null;

  const { data: teams, refetch: refetchTeams } = useFetch<TeamOption[]>(
    seasonId ? `/tournaments/${seasonId}/teams` : null,
  );

  const { data: season } = useFetch<{ tournament_config: TournamentConfig | null }>(
    seasonId ? `/seasons/${seasonId}` : null,
  );

  // Local edit state (team_id -> group letter or "")
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // Reset when teams reload
  useEffect(() => {
    if (teams) {
      const init: Record<number, string> = {};
      for (const t of teams) {
        init[t.id] = t.tournament_group ?? "";
      }
      setEdits(init);
    }
  }, [teams]);

  const groupCount = season?.tournament_config?.groups?.count ?? 12;
  const teamsPerGroup = season?.tournament_config?.groups?.teams_per_group ?? 4;
  const visibleGroups = GROUP_LETTERS.slice(0, groupCount);

  // Compute who is currently assigned to each group (from edits)
  const grouped = useMemo(() => {
    const byGroup: Record<string, TeamOption[]> = {};
    for (const g of visibleGroups) byGroup[g] = [];
    const unassigned: TeamOption[] = [];
    for (const t of teams ?? []) {
      const g = edits[t.id] ?? "";
      if (g && byGroup[g]) {
        byGroup[g].push(t);
      } else {
        unassigned.push(t);
      }
    }
    return { byGroup, unassigned };
  }, [teams, edits, visibleGroups]);

  // Validation: warn if some group is over the limit
  const overflows = visibleGroups.filter(
    (g) => grouped.byGroup[g].length > teamsPerGroup,
  );

  async function handleSave() {
    if (!seasonId || !teams) return;
    setSaving(true);
    setMessage(null);
    try {
      const assignments = teams
        .filter((t) => (t.tournament_group ?? "") !== (edits[t.id] ?? ""))
        .map((t) => ({
          team_id: t.id,
          group_name: edits[t.id] || null,
        }));
      if (assignments.length === 0) {
        setMessage("Sin cambios");
        setTimeout(() => setMessage(null), 3000);
        return;
      }
      await apiClient.put(`/tournaments/admin/${seasonId}/teams/groups`, {
        assignments,
      });
      await refetchTeams();
      setMessage(`${assignments.length} equipo(s) actualizado(s)`);
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  if (!teams) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">Cargando equipos...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-vpv-text">Asignar grupos</h1>
          <p className="text-xs text-vpv-text-muted">
            {teams.length} equipos · {groupCount} grupos de {teamsPerGroup} ·{" "}
            <span
              className={
                grouped.unassigned.length === 0
                  ? "text-green-500"
                  : "text-amber-500"
              }
            >
              {grouped.unassigned.length} sin asignar
            </span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {message && (
            <span className="text-xs text-vpv-text-muted">{message}</span>
          )}
          <button
            onClick={handleSave}
            disabled={saving || overflows.length > 0}
            className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
          >
            {saving ? "Guardando..." : "Guardar"}
          </button>
        </div>
      </div>

      {overflows.length > 0 && (
        <div className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          Grupos con mas de {teamsPerGroup} equipos: {overflows.join(", ")}
        </div>
      )}

      {/* Unassigned pool */}
      {grouped.unassigned.length > 0 && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
          <div className="border-b border-vpv-border px-4 py-2">
            <h2 className="text-sm font-semibold text-vpv-text">
              Sin asignar ({grouped.unassigned.length})
            </h2>
          </div>
          <div className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-3 lg:grid-cols-4">
            {grouped.unassigned.map((t) => (
              <TeamRow
                key={t.id}
                team={t}
                value={edits[t.id] ?? ""}
                groups={visibleGroups}
                onChange={(v) =>
                  setEdits((prev) => ({ ...prev, [t.id]: v }))
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* Groups grid */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {visibleGroups.map((g) => {
          const overLimit = grouped.byGroup[g].length > teamsPerGroup;
          return (
            <div
              key={g}
              className={`overflow-hidden rounded-lg border bg-vpv-card ${
                overLimit ? "border-red-500/60" : "border-vpv-card-border"
              }`}
            >
              <div className="flex items-center justify-between border-b border-vpv-border bg-vpv-bg/50 px-4 py-2">
                <h2 className="font-semibold text-vpv-text">Grupo {g}</h2>
                <span
                  className={`text-xs ${overLimit ? "text-red-400" : "text-vpv-text-muted"}`}
                >
                  {grouped.byGroup[g].length} / {teamsPerGroup}
                </span>
              </div>
              <div className="space-y-1 p-2">
                {grouped.byGroup[g].length === 0 ? (
                  <p className="px-2 py-3 text-center text-xs text-vpv-text-muted">
                    Vacio
                  </p>
                ) : (
                  grouped.byGroup[g].map((t) => (
                    <TeamRow
                      key={t.id}
                      team={t}
                      value={edits[t.id] ?? ""}
                      groups={visibleGroups}
                      onChange={(v) =>
                        setEdits((prev) => ({ ...prev, [t.id]: v }))
                      }
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TeamRow({
  team,
  value,
  groups,
  onChange,
}: {
  team: TeamOption;
  value: string;
  groups: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded border border-vpv-border bg-vpv-bg px-2 py-1">
      {team.logo_path && (
        <img src={team.logo_path} alt="" className="h-5 w-5 shrink-0" />
      )}
      <span className="min-w-0 flex-1 truncate text-xs text-vpv-text">
        {team.short_name ?? team.name}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-vpv-border bg-vpv-card px-1 py-0.5 text-xs text-vpv-text"
      >
        <option value="">—</option>
        {groups.map((g) => (
          <option key={g} value={g}>
            {g}
          </option>
        ))}
      </select>
    </div>
  );
}
