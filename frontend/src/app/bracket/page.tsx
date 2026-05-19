"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SkeletonCards } from "@/components/ui/skeleton";
import type { BracketResponse, BracketMatch } from "@/types";

export default function BracketPage() {
  const { isTournamentContext, loading: seasonLoading } = useSeason();

  if (!seasonLoading && !isTournamentContext) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">
          Esta vista solo aplica a torneos con fase eliminatoria.
        </p>
      </div>
    );
  }

  return <BracketContent />;
}

function BracketContent() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading, error } = useFetch<BracketResponse>(
    selectedSeason ? `/tournaments/${selectedSeason.id}/bracket` : null,
  );

  if (seasonLoading || loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 animate-pulse rounded bg-vpv-border" />
        <SkeletonCards count={3} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">No se pudo cargar el bracket</p>
      </div>
    );
  }

  if (data.rounds.length === 0) {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-vpv-text">Cuadro de eliminatorias</h1>
          <p className="mt-1 text-vpv-text-muted">{data.season_name}</p>
        </div>
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
          <p className="text-vpv-text-muted">
            El cuadro se rellena conforme avanza el torneo. Aun no hay rondas configuradas.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-vpv-text">Cuadro de eliminatorias</h1>
        <p className="mt-1 text-vpv-text-muted">{data.season_name}</p>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-2">
        {data.rounds.map((round) => (
          <RoundColumn key={round.matchday} round={round} />
        ))}
      </div>
    </div>
  );
}

function RoundColumn({ round }: { round: BracketResponse["rounds"][number] }) {
  return (
    <div className="flex min-w-[240px] flex-1 flex-col gap-3">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-vpv-text-muted">
        {round.name} <span className="text-xs">(J{round.matchday})</span>
      </h2>
      {round.matches.length === 0 ? (
        <div className="rounded-lg border border-dashed border-vpv-border p-4 text-center text-xs text-vpv-text-muted">
          Sin partidos
        </div>
      ) : (
        round.matches.map((m, i) => <MatchCard key={m.match_id ?? i} match={m} />)
      )}
    </div>
  );
}

function MatchCard({ match }: { match: BracketMatch }) {
  return (
    <div
      className={`rounded-lg border bg-vpv-card p-3 ${
        match.played ? "border-vpv-card-border" : "border-dashed border-vpv-border"
      }`}
    >
      <TeamRow
        name={match.home_team_name}
        logo={match.home_logo}
        score={match.home_score}
        played={match.played}
      />
      <div className="my-1 border-t border-vpv-border/30" />
      <TeamRow
        name={match.away_team_name}
        logo={match.away_logo}
        score={match.away_score}
        played={match.played}
      />
    </div>
  );
}

function TeamRow({
  name,
  logo,
  score,
  played,
}: {
  name: string | null;
  logo: string | null;
  score: number | null;
  played: boolean;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {logo && <img src={logo} alt="" className="h-5 w-5 shrink-0" />}
      <span
        className={`flex-1 truncate ${
          name ? "text-vpv-text" : "text-vpv-text-muted italic"
        }`}
      >
        {name ?? "Por determinar"}
      </span>
      {played && (
        <span className="font-bold tabular-nums text-vpv-text">{score ?? 0}</span>
      )}
    </div>
  );
}
