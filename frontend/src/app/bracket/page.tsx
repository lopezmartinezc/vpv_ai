"use client";

import { useMemo } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SkeletonCards } from "@/components/ui/skeleton";
import { TournamentHero } from "@/components/tournament/tournament-hero";
import { CountryFlag } from "@/components/ui/country-flag";
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
        <p className="text-vpv-text-muted">No se pudo cargar el cuadro</p>
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
      <WorldCupBracket data={data} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Two-sided FIFA-style bracket
// ---------------------------------------------------------------------------

interface MatchByCode {
  [code: string]: BracketMatch;
}

interface BracketLayout {
  left: { r32: string[]; r16: string[]; qf: string[]; sf: string }; // codes
  right: { r32: string[]; r16: string[]; qf: string[]; sf: string };
  final: string;
  third: string | null;
}

function WorldCupBracket({ data }: { data: BracketResponse }) {
  const matchByCode: MatchByCode = useMemo(() => {
    const m: MatchByCode = {};
    for (const round of data.rounds) {
      for (const match of round.matches) {
        if (match.match_code) m[match.match_code] = match;
      }
    }
    return m;
  }, [data]);

  const layout = useMemo(() => computeLayout(data, matchByCode), [data, matchByCode]);

  if (!layout) {
    // No "semis" round or can't compute layout — fall back to linear view
    return <LinearBracket data={data} />;
  }

  return (
    <>
      {/* Desktop: 2-sided bracket */}
      <div className="hidden md:block">
        <TwoSidedBracket layout={layout} matchByCode={matchByCode} />
      </div>
      {/* Mobile: linear scrollable */}
      <div className="md:hidden">
        <LinearBracket data={data} />
      </div>
    </>
  );
}

function computeLayout(data: BracketResponse, matchByCode: MatchByCode): BracketLayout | null {
  const semis = data.rounds.find((r) => r.matches.length === 2 && r.matches.every((m) => m.match_code?.startsWith("M10") || isSemiRound(r.name)));
  // We rely on the pairings structure: find the final + 3rd round (last) and the previous (semis)
  if (data.rounds.length < 2) return null;
  // Pick the round of size 2 *before* the last as semis (last has final+3rd, both size 2)
  const lastIdx = data.rounds.length - 1;
  const finalRound = data.rounds[lastIdx];
  const semisRound = data.rounds[lastIdx - 1];
  if (!semisRound || semisRound.matches.length !== 2 || finalRound.matches.length === 0) return null;
  void semis;

  const semiL = semisRound.matches[0]?.match_code;
  const semiR = semisRound.matches[1]?.match_code;
  if (!semiL || !semiR) return null;

  // Walk back from semi to QF, R16, R32 using placeholders (which encode the parent match codes)
  function parents(code: string): [string, string] | null {
    const m = matchByCode[code];
    if (!m) return null;
    const h = parsePlaceholder(m.home_placeholder);
    const a = parsePlaceholder(m.away_placeholder);
    if (h && a) return [h, a];
    return null;
  }

  function trace(rootCode: string): { qf: string[]; r16: string[]; r32: string[] } | null {
    const qfPair = parents(rootCode);
    if (!qfPair) return null;
    const r16Codes: string[] = [];
    const r32Codes: string[] = [];
    for (const qf of qfPair) {
      const r16Pair = parents(qf);
      if (!r16Pair) return null;
      for (const r16 of r16Pair) {
        const r32Pair = parents(r16);
        if (!r32Pair) return null;
        for (const r32 of r32Pair) {
          r32Codes.push(r32);
        }
        r16Codes.push(r16);
      }
    }
    return { qf: qfPair, r16: r16Codes, r32: r32Codes };
  }

  const leftTrace = trace(semiL);
  const rightTrace = trace(semiR);
  if (!leftTrace || !rightTrace) return null;

  // Pick the final and 3rd-place match codes from the final round
  // Convention: code with higher number = final (M104 > M103)
  const finalCodes = finalRound.matches
    .map((m) => m.match_code ?? "")
    .filter(Boolean)
    .sort((a, b) => matchNumber(b) - matchNumber(a));
  const finalCode = finalCodes[0] ?? "";
  const thirdCode = finalCodes[1] ?? null;

  return {
    left: { ...leftTrace, sf: semiL },
    right: { ...rightTrace, sf: semiR },
    final: finalCode,
    third: thirdCode,
  };
}

function isSemiRound(name: string): boolean {
  const n = name.toLowerCase();
  return n.includes("semi");
}

function matchNumber(code: string): number {
  const m = /\d+/.exec(code);
  return m ? Number(m[0]) : 0;
}

function parsePlaceholder(p: string | null | undefined): string | null {
  if (!p) return null;
  if (p.startsWith("W") || p.startsWith("L")) return `M${p.slice(1)}`;
  return null;
}

function TwoSidedBracket({
  layout,
  matchByCode,
}: {
  layout: BracketLayout;
  matchByCode: MatchByCode;
}) {
  // Layout: 9 columns
  //  left R32 | left R16 | left QF | left SF | CENTER | right SF | right QF | right R16 | right R32
  // Each column uses flex column + space-around to align cards to midpoints.
  const renderColumn = (codes: string[], label: string, mdNum: number) => (
    <div className="flex min-w-[170px] flex-1 flex-col">
      <div className="mb-2 text-center text-[10px] font-semibold uppercase tracking-widest text-vpv-text-muted">
        {label} · J{mdNum}
      </div>
      <div className="flex h-full flex-col justify-around gap-3">
        {codes.map((code) => {
          const m = matchByCode[code];
          if (!m) {
            return (
              <div key={code} className="rounded border border-dashed border-vpv-border p-2 text-[10px] text-vpv-text-muted">
                {code}
              </div>
            );
          }
          return <CompactMatchCard key={code} match={m} />;
        })}
      </div>
    </div>
  );

  // Round names from data — fall back to defaults if not present
  const roundNames = ["16avos", "Octavos", "Cuartos", "Semis", "Final"];
  const roundMatchdays = [4, 5, 6, 7, 8];

  // Reverse R32 codes for right side so they appear "mirrored" — already in tree order from trace,
  // which produces a natural top-to-bottom listing matching pair adjacency.
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex min-h-[680px] items-stretch gap-2">
        {/* LEFT SIDE */}
        {renderColumn(layout.left.r32, roundNames[0], roundMatchdays[0])}
        {renderColumn(layout.left.r16, roundNames[1], roundMatchdays[1])}
        {renderColumn(layout.left.qf, roundNames[2], roundMatchdays[2])}
        {renderColumn([layout.left.sf], roundNames[3], roundMatchdays[3])}

        {/* CENTER: Final + 3rd place */}
        <div className="flex min-w-[200px] flex-col items-center justify-center gap-4 px-2">
          <div className="text-center text-[10px] font-semibold uppercase tracking-widest text-vpv-text-muted">
            {roundNames[4]} · J{roundMatchdays[4]}
          </div>
          {layout.final && matchByCode[layout.final] && (
            <FinalCard match={matchByCode[layout.final]} />
          )}
          {layout.third && matchByCode[layout.third] && (
            <ThirdPlaceCard match={matchByCode[layout.third]} />
          )}
        </div>

        {/* RIGHT SIDE (mirrored) */}
        {renderColumn([layout.right.sf], roundNames[3], roundMatchdays[3])}
        {renderColumn(layout.right.qf, roundNames[2], roundMatchdays[2])}
        {renderColumn(layout.right.r16, roundNames[1], roundMatchdays[1])}
        {renderColumn(layout.right.r32, roundNames[0], roundMatchdays[0])}
      </div>
    </div>
  );
}

function CompactMatchCard({ match }: { match: BracketMatch }) {
  const homeWon =
    match.played &&
    match.home_score !== null &&
    match.away_score !== null &&
    match.home_score > match.away_score;
  const awayWon =
    match.played &&
    match.home_score !== null &&
    match.away_score !== null &&
    match.away_score > match.home_score;

  return (
    <div
      className={`group rounded border bg-vpv-card text-xs shadow-sm transition-all hover:shadow-md ${
        match.played ? "border-vpv-card-border" : "border-dashed border-vpv-border"
      }`}
    >
      {match.match_code && (
        <div className="border-b border-vpv-border/40 bg-vpv-bg/40 px-2 py-0.5 text-center text-[9px] font-semibold uppercase tracking-wider text-vpv-text-muted">
          {match.label ?? `Partido ${matchNumber(match.match_code)}`}
        </div>
      )}
      <CompactTeamRow
        name={match.home_team_name}
        logo={match.home_logo}
        score={match.home_score}
        played={match.played}
        placeholder={match.home_placeholder}
        provisionalName={match.home_provisional_team_name}
        provisionalLogo={match.home_provisional_logo}
        won={homeWon}
      />
      <div className="border-t border-vpv-border/30" />
      <CompactTeamRow
        name={match.away_team_name}
        logo={match.away_logo}
        score={match.away_score}
        played={match.played}
        placeholder={match.away_placeholder}
        provisionalName={match.away_provisional_team_name}
        provisionalLogo={match.away_provisional_logo}
        won={awayWon}
      />
    </div>
  );
}

function FinalCard({ match }: { match: BracketMatch }) {
  return (
    <div className="w-full rounded-lg border-2 border-amber-400/60 bg-gradient-to-br from-amber-500/10 to-amber-700/10 p-3 shadow-lg">
      <p className="mb-2 text-center text-[10px] font-semibold uppercase tracking-widest text-amber-400">
        🏆 Final
      </p>
      <CompactMatchCardBody match={match} />
    </div>
  );
}

function ThirdPlaceCard({ match }: { match: BracketMatch }) {
  return (
    <div className="w-full rounded-lg border border-zinc-500/30 bg-zinc-500/5 p-3">
      <p className="mb-1 text-center text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
        🥉 3er puesto
      </p>
      <CompactMatchCardBody match={match} />
    </div>
  );
}

function CompactMatchCardBody({ match }: { match: BracketMatch }) {
  const homeWon =
    match.played &&
    match.home_score !== null &&
    match.away_score !== null &&
    match.home_score > match.away_score;
  const awayWon =
    match.played &&
    match.home_score !== null &&
    match.away_score !== null &&
    match.away_score > match.home_score;
  return (
    <>
      <CompactTeamRow
        name={match.home_team_name}
        logo={match.home_logo}
        score={match.home_score}
        played={match.played}
        placeholder={match.home_placeholder}
        provisionalName={match.home_provisional_team_name}
        provisionalLogo={match.home_provisional_logo}
        won={homeWon}
      />
      <div className="my-0.5 border-t border-vpv-border/30" />
      <CompactTeamRow
        name={match.away_team_name}
        logo={match.away_logo}
        score={match.away_score}
        played={match.played}
        placeholder={match.away_placeholder}
        provisionalName={match.away_provisional_team_name}
        provisionalLogo={match.away_provisional_logo}
        won={awayWon}
      />
    </>
  );
}

function CompactTeamRow({
  name,
  logo,
  score,
  played,
  placeholder,
  provisionalName,
  provisionalLogo,
  won,
}: {
  name: string | null;
  logo: string | null;
  score: number | null;
  played: boolean;
  placeholder?: string | null;
  provisionalName?: string | null;
  provisionalLogo?: string | null;
  won?: boolean;
}) {
  // Priority: official team → provisional team (italic) → placeholder text
  const displayName = name ?? provisionalName ?? null;
  const displayLogo = name ? logo : provisionalLogo ?? null;
  const isProvisional = !name && !!provisionalName;
  const label = displayName ?? placeholderLabel(placeholder);
  const isPlaceholder = !displayName;
  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-1 text-xs ${
        played && !won ? "opacity-50" : ""
      }`}
    >
      {displayName ? (
        <CountryFlag
          teamName={displayName}
          fallbackLogo={displayLogo}
          size={16}
          className="!rounded-[2px]"
        />
      ) : (
        <span className="h-3 w-4 shrink-0" />
      )}
      <span
        className={`min-w-0 flex-1 truncate ${
          isPlaceholder
            ? "italic text-vpv-text-muted"
            : isProvisional
              ? "italic text-vpv-text-muted/90"
              : "text-vpv-text"
        } ${won ? "font-bold text-green-500" : ""}`}
        title={isProvisional ? `Provisional · ${placeholderLabel(placeholder)}` : undefined}
      >
        {label}
      </span>
      {played && (
        <span
          className={`shrink-0 font-bold tabular-nums ${
            won ? "text-green-500" : "text-vpv-text"
          }`}
        >
          {score ?? 0}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fallback: linear horizontal bracket (mobile / when computeLayout fails)
// ---------------------------------------------------------------------------

function LinearBracket({ data }: { data: BracketResponse }) {
  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {data.rounds.map((round) => (
        <div key={round.matchday} className="flex min-w-[220px] flex-1 flex-col gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-vpv-text-muted">
            {round.name} · J{round.matchday}
          </h2>
          {round.matches.length === 0 ? (
            <div className="rounded-lg border border-dashed border-vpv-border p-4 text-center text-xs text-vpv-text-muted">
              Sin partidos
            </div>
          ) : (
            round.matches.map((m, i) => (
              <CompactMatchCard key={m.match_id ?? `${round.matchday}-${i}`} match={m} />
            ))
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Placeholder label translation (shared with linear view via CompactMatchCard)
// ---------------------------------------------------------------------------

function placeholderLabel(p: string | null | undefined): string {
  if (!p) return "Por determinar";
  if (p.startsWith("1") && p.length === 2) return `1º Grupo ${p[1]}`;
  if (p.startsWith("2") && p.length === 2) return `2º Grupo ${p[1]}`;
  if (p.startsWith("3:")) return `Mejor 3º (${p.slice(2)})`;
  if (p.startsWith("W")) return `Ganador M${p.slice(1)}`;
  if (p.startsWith("L")) return `Perdedor M${p.slice(1)}`;
  return p;
}
