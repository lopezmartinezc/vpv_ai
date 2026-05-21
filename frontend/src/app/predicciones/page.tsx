"use client";

import { Fragment, useMemo, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useAuth } from "@/contexts/auth-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient } from "@/lib/api-client";
import { SkeletonCards } from "@/components/ui/skeleton";
import { TournamentHero } from "@/components/tournament/tournament-hero";
import { CountryFlag } from "@/components/ui/country-flag";
import type {
  BracketPredictions,
  BracketMatch,
  BracketResponse,
  PredictionsListResponse,
  TournamentPrediction,
} from "@/types";

interface TeamOption {
  id: number;
  name: string;
  short_name: string | null;
  logo_path: string | null;
  tournament_group: string | null;
}

export default function PrediccionesPage() {
  const { isTournamentContext, loading: seasonLoading } = useSeason();

  if (!seasonLoading && !isTournamentContext) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">
          Las predicciones solo aplican a torneos.
        </p>
      </div>
    );
  }

  return <PrediccionesContent />;
}

function PrediccionesContent() {
  const { selectedSeason } = useSeason();
  const { user } = useAuth();
  const isAdmin = user?.isAdmin === true;
  const isLogged = user != null;
  const seasonId = selectedSeason?.id ?? null;

  const { data: teams } = useFetch<TeamOption[]>(
    seasonId ? `/tournaments/${seasonId}/teams` : null,
  );
  const { data: bracket } = useFetch<BracketResponse>(
    seasonId ? `/tournaments/${seasonId}/bracket` : null,
  );
  const {
    data: allPreds,
    loading,
    error,
    refetch,
  } = useFetch<PredictionsListResponse>(
    seasonId ? `/tournaments/${seasonId}/predictions` : null,
  );
  const { data: status } = useFetch<{
    locked: boolean;
    deadline_at: string | null;
  }>(seasonId ? `/tournaments/${seasonId}/predictions/status` : null);

  const teamsById = useMemo(() => {
    const m: Record<number, TeamOption> = {};
    for (const t of teams ?? []) m[t.id] = t;
    return m;
  }, [teams]);

  return (
    <div className="space-y-5">
      <TournamentHero
        title="Predicciones"
        subtitle="Ranking de aciertos del torneo"
      />

      {/* Header acciones */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-vpv-text-muted">
          {status?.locked === true ? (
            <span className="font-semibold text-amber-400">
              Predicciones cerradas — el torneo ya empezó
            </span>
          ) : status?.deadline_at ? (
            <span>
              Predicciones abiertas hasta{" "}
              <strong>{new Date(status.deadline_at).toLocaleString("es-ES")}</strong>
            </span>
          ) : (
            <span>Predicciones abiertas</span>
          )}
        </div>
        {isLogged && (
          <a
            href="/mis-predicciones"
            className="rounded-md bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80"
          >
            {status?.locked === true ? "Ver mi predicción" : "Mis predicciones"}
          </a>
        )}
      </div>

      <PublicRanking
        data={allPreds}
        loading={loading}
        error={error}
        isAdmin={isAdmin}
        seasonId={seasonId}
        teamsById={teamsById}
        bracket={bracket}
        onRecalculated={refetch}
      />
    </div>
  );
}

// =============================================================================
// Public ranking: table + expandable details per participant
// =============================================================================

function PublicRanking({
  data,
  loading,
  error,
  isAdmin,
  seasonId,
  teamsById,
  bracket,
  onRecalculated,
}: {
  data: PredictionsListResponse | null | undefined;
  loading?: boolean;
  error?: boolean;
  isAdmin?: boolean;
  seasonId?: number | null;
  teamsById: Record<number, TeamOption>;
  bracket: BracketResponse | null | undefined;
  onRecalculated?: () => void | Promise<unknown>;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [recalcing, setRecalcing] = useState(false);
  const [recalcMsg, setRecalcMsg] = useState<string | null>(null);

  async function handleRecalc() {
    if (!seasonId) return;
    setRecalcing(true);
    setRecalcMsg(null);
    try {
      await apiClient.post(
        `/tournaments/admin/${seasonId}/predictions/recalculate`,
        {},
      );
      setRecalcMsg("Puntos recalculados");
      await onRecalculated?.();
      setTimeout(() => setRecalcMsg(null), 3000);
    } catch {
      setRecalcMsg("Error al recalcular");
    } finally {
      setRecalcing(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
        <SkeletonCards count={4} />
      </div>
    );
  }
  if (error) return null;
  if (!data || data.predictions.length === 0) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center text-sm text-vpv-text-muted">
        Aún no hay predicciones registradas.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-center justify-between border-b border-vpv-border px-4 py-3">
        <h2 className="font-semibold text-vpv-text">Ranking de predicciones</h2>
        {isAdmin && (
          <div className="flex items-center gap-2">
            {recalcMsg && (
              <span className="text-xs text-vpv-text-muted">{recalcMsg}</span>
            )}
            <button
              onClick={handleRecalc}
              disabled={recalcing}
              className="rounded-md bg-vpv-accent px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {recalcing ? "Recalculando..." : "Recalcular puntos"}
            </button>
          </div>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-bg/50 text-xs text-vpv-text-muted">
              <th className="w-8 px-2 py-2"></th>
              <th className="px-3 py-2 text-left">Participante</th>
              <th className="px-3 py-2 text-left">Campeón</th>
              <th className="px-3 py-2 text-left">Sorpresa</th>
              <th className="px-3 py-2 text-left">Goleador</th>
              <th className="px-3 py-2 text-left">MVP</th>
              <th className="px-3 py-2 text-right">Bonus</th>
            </tr>
          </thead>
          <tbody>
            {data.predictions.map((p) => {
              const isOpen = expandedId === p.id;
              return (
                <Fragment key={p.id}>
                  <tr
                    className="cursor-pointer border-b border-vpv-border last:border-0 hover:bg-vpv-bg/30"
                    onClick={() => setExpandedId(isOpen ? null : p.id)}
                  >
                    <td className="px-2 py-2 text-center text-vpv-text-muted">
                      <span aria-hidden="true">{isOpen ? "▾" : "▸"}</span>
                    </td>
                    <td className="px-3 py-2 font-medium text-vpv-text">
                      {p.display_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-vpv-text-muted">
                      <div className="flex items-center gap-1.5">
                        {p.winner_team_name && (
                          <CountryFlag teamName={p.winner_team_name} size={16} />
                        )}
                        {p.winner_team_name ?? "—"}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-vpv-text-muted">
                      <div className="flex items-center gap-1.5">
                        {p.dark_horse_team_name && (
                          <CountryFlag teamName={p.dark_horse_team_name} size={16} />
                        )}
                        {p.dark_horse_team_name ?? "—"}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-vpv-text-muted">
                      {p.top_scorer_player_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-vpv-text-muted">
                      {p.best_player_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-bold tabular-nums text-vpv-text">
                      {p.bonus_points}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="border-b border-vpv-border last:border-0 bg-vpv-bg/20">
                      <td colSpan={7} className="px-4 py-3">
                        <PredictionDetail
                          prediction={p}
                          teamsById={teamsById}
                          bracket={bracket}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =============================================================================
// Detalle expandido de una predicción (grupos + best thirds + bracket)
// =============================================================================

function PredictionDetail({
  prediction,
  teamsById,
  bracket,
}: {
  prediction: TournamentPrediction;
  teamsById: Record<number, TeamOption>;
  bracket: BracketResponse | null | undefined;
}) {
  const bp: BracketPredictions = prediction.bracket_predictions ?? {};
  const groups = bp.groups ?? {};
  const bestThirds = bp.best_thirds ?? [];
  const matchWinners = bp.match_winners ?? {};

  const groupLetters = Object.keys(groups).sort();
  const hasGroups = groupLetters.length > 0;
  const hasBestThirds = bestThirds.length > 0;
  const hasMatchWinners = Object.keys(matchWinners).length > 0;

  if (!hasGroups && !hasBestThirds && !hasMatchWinners && !prediction.notes) {
    return (
      <p className="text-center text-xs italic text-vpv-text-muted">
        Sin detalle adicional.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {prediction.notes && (
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
            Notas
          </h3>
          <p className="rounded bg-vpv-card px-2 py-1.5 text-sm text-vpv-text">
            {prediction.notes}
          </p>
        </div>
      )}

      {hasGroups && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
            Orden de grupos
          </h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {groupLetters.map((letter) => (
              <GroupOrderDetail
                key={letter}
                letter={letter}
                order={groups[letter] ?? []}
                teamsById={teamsById}
              />
            ))}
          </div>
        </div>
      )}

      {hasBestThirds && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
            Mejores 3os ({bestThirds.length}/8)
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {bestThirds.sort().map((letter) => {
              const third = groups[letter]?.[2];
              const team = third ? teamsById[third] : null;
              return (
                <span
                  key={letter}
                  className="inline-flex items-center gap-1 rounded border border-green-500/40 bg-green-500/10 px-2 py-0.5 text-[11px] text-green-400"
                >
                  <strong>{letter}</strong>
                  {team && <CountryFlag teamName={team.name} size={14} />}
                  {team?.short_name ?? team?.name ?? "—"}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {hasMatchWinners && bracket && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
            Ganadores eliminatoria
          </h3>
          <KnockoutWinnersList
            matchWinners={matchWinners}
            bracket={bracket}
            teamsById={teamsById}
          />
        </div>
      )}
    </div>
  );
}

function GroupOrderDetail({
  letter,
  order,
  teamsById,
}: {
  letter: string;
  order: (number | null)[];
  teamsById: Record<number, TeamOption>;
}) {
  return (
    <div className="rounded border border-vpv-border bg-vpv-card px-2 py-1.5">
      <p className="mb-1 text-center text-[11px] font-semibold text-vpv-text-muted">
        Grupo {letter}
      </p>
      <ol className="space-y-0.5 text-xs">
        {[0, 1, 2, 3].map((idx) => {
          const id = order[idx];
          const team = id ? teamsById[id] : null;
          return (
            <li key={idx} className="flex items-center gap-1.5">
              <span className="w-5 shrink-0 text-vpv-text-muted">
                {["1º", "2º", "3º", "4º"][idx]}
              </span>
              {team ? (
                <>
                  <CountryFlag teamName={team.name} fallbackLogo={team.logo_path} size={14} />
                  <span className="min-w-0 flex-1 truncate text-vpv-text">
                    {team.short_name ?? team.name}
                  </span>
                </>
              ) : (
                <span className="italic text-vpv-text-muted">—</span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function KnockoutWinnersList({
  matchWinners,
  bracket,
  teamsById,
}: {
  matchWinners: Record<string, number | null>;
  bracket: BracketResponse;
  teamsById: Record<number, TeamOption>;
}) {
  // Group by round (using bracket.rounds matchday)
  const matchByCode: Record<string, BracketMatch & { round: string }> = {};
  for (const round of bracket.rounds) {
    for (const m of round.matches) {
      if (m.match_code)
        matchByCode[m.match_code] = { ...m, round: round.name };
    }
  }
  const byRound: Record<string, { code: string; teamId: number }[]> = {};
  for (const [code, teamId] of Object.entries(matchWinners)) {
    if (teamId == null) continue;
    const roundName = matchByCode[code]?.round ?? "Otros";
    (byRound[roundName] ??= []).push({ code, teamId });
  }

  return (
    <div className="space-y-2">
      {Object.entries(byRound).map(([roundName, picks]) => (
        <div key={roundName}>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
            {roundName}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {picks.map(({ code, teamId }) => {
              const team = teamsById[teamId];
              return (
                <span
                  key={code}
                  className="inline-flex items-center gap-1 rounded border border-vpv-border bg-vpv-card px-2 py-0.5 text-[11px] text-vpv-text"
                >
                  <span className="text-vpv-text-muted">{code}</span>
                  {team && <CountryFlag teamName={team.name} size={14} />}
                  {team?.short_name ?? team?.name ?? `#${teamId}`}
                </span>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
