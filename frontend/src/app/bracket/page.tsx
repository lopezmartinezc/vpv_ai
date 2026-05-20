"use client";

import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SkeletonCards } from "@/components/ui/skeleton";
import { TournamentHero } from "@/components/tournament/tournament-hero";
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
      <div className="space-y-6">
        <TournamentHero
          title="Cuadro de eliminatorias"
          subtitle="Octavos hasta la final"
        />
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
      <TournamentHero
        title="Cuadro de eliminatorias"
        subtitle="Octavos hasta la final"
      />

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
      {(match.label || match.match_code) && (
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
          {match.label ?? match.match_code}
        </p>
      )}
      <TeamRow
        name={match.home_team_name}
        logo={match.home_logo}
        score={match.home_score}
        played={match.played}
        placeholder={match.home_placeholder}
      />
      <div className="my-1 border-t border-vpv-border/30" />
      <TeamRow
        name={match.away_team_name}
        logo={match.away_logo}
        score={match.away_score}
        played={match.played}
        placeholder={match.away_placeholder}
      />
    </div>
  );
}

function placeholderLabel(p: string | null | undefined): string {
  if (!p) return "Por determinar";
  // FIFA notation -> human-friendly Spanish labels:
  //   "1A"       -> "1º Grupo A"   (winner of Group A)
  //   "2A"       -> "2º Grupo A"   (runner-up of Group A)
  //   "3:ABCDF"  -> "Mejor 3º (ABCDF)" (best 3rd-placed among those groups)
  //   "W74"      -> "Ganador M74"  (winner of Match 74)
  //   "L101"     -> "Perdedor M101"  (loser of Match 101)
  if (p.startsWith("1") && p.length === 2) return `1º Grupo ${p[1]}`;
  if (p.startsWith("2") && p.length === 2) return `2º Grupo ${p[1]}`;
  if (p.startsWith("3:")) return `Mejor 3º (${p.slice(2)})`;
  if (p.startsWith("W")) return `Ganador M${p.slice(1)}`;
  if (p.startsWith("L")) return `Perdedor M${p.slice(1)}`;
  return p;
}

function TeamRow({
  name,
  logo,
  score,
  played,
  placeholder,
}: {
  name: string | null;
  logo: string | null;
  score: number | null;
  played: boolean;
  placeholder?: string | null;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {logo && <img src={logo} alt="" className="h-5 w-5 shrink-0" />}
      <span
        className={`flex-1 truncate ${
          name ? "text-vpv-text" : "italic text-vpv-text-muted"
        }`}
      >
        {name ?? placeholderLabel(placeholder)}
      </span>
      {played && (
        <span className="font-bold tabular-nums text-vpv-text">{score ?? 0}</span>
      )}
    </div>
  );
}
