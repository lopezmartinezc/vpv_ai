"use client";

import { useState } from "react";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { DreamTeamResponse, HighlightPlayer, MatchdayHighlightsResponse } from "@/types";

const POSITION_COLORS: Record<string, string> = {
  POR: "bg-amber-600/20 text-amber-400",
  DEF: "bg-blue-600/20 text-blue-400",
  MED: "bg-green-600/20 text-green-400",
  DEL: "bg-red-600/20 text-red-400",
};

const HIGHLIGHT_CARDS: {
  key: keyof MatchdayHighlightsResponse;
  label: string;
  icon: string;
  color: string;
  detail: (p: HighlightPlayer) => string;
}[] = [
  {
    key: "mvp",
    label: "MVP",
    icon: "\u2B50",
    color: "border-amber-500/40 bg-amber-500/10",
    detail: (p) => `${p.points} pts`,
  },
  {
    key: "top_scorer",
    label: "Goleador",
    icon: "\u26BD",
    color: "border-green-500/40 bg-green-500/10",
    detail: (p) => `${p.goals} gol${p.goals !== 1 ? "es" : ""}`,
  },
  {
    key: "top_assister",
    label: "Asistente",
    icon: "\uD83C\uDFAF",
    color: "border-blue-500/40 bg-blue-500/10",
    detail: (p) => `${p.assists} asist.`,
  },
  {
    key: "flop",
    label: "Flop",
    icon: "\uD83D\uDCC9",
    color: "border-red-500/40 bg-red-500/10",
    detail: (p) => `${p.points} pts`,
  },
];

export function MatchdayHighlights({
  highlights,
}: {
  highlights: MatchdayHighlightsResponse;
}) {
  const [showTeam, setShowTeam] = useState<"dream" | "nightmare" | null>(null);

  const cards = HIGHLIGHT_CARDS.filter(
    (c) => highlights[c.key] != null,
  );

  const hasBadges = cards.length > 0;
  const hasTeams = highlights.dream_team != null || highlights.nightmare_team != null;

  if (!hasBadges && !hasTeams) return null;

  return (
    <div className="space-y-3">
      {/* Individual highlights */}
      {hasBadges && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {cards.map((card) => {
            const player = highlights[card.key] as HighlightPlayer;
            return (
              <div
                key={card.key}
                className={`rounded-lg border px-3 py-2.5 ${card.color}`}
              >
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="text-sm" aria-hidden="true">
                    {card.icon}
                  </span>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
                    {card.label}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <PlayerAvatar
                    photoPath={player.photo_path}
                    name={player.player_name}
                    size={28}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-vpv-text">
                      {player.player_name}
                    </p>
                    <p className="text-[10px] text-vpv-text-muted">
                      {player.team_name} &middot; {card.detail(player)}
                    </p>
                  </div>
                </div>
                <p className="mt-1 text-[10px] text-vpv-text-muted/70">
                  {player.owner_name}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* Dream / Nightmare team toggles */}
      {hasTeams && (
        <div className="flex gap-2">
          {highlights.dream_team && (
            <button
              onClick={() => setShowTeam(showTeam === "dream" ? null : "dream")}
              className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                showTeam === "dream"
                  ? "border-amber-500 bg-amber-500/20 text-amber-400"
                  : "border-vpv-border bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              <span aria-hidden="true">{"\u2B50"}</span>
              Mejor XI ({highlights.dream_team.total_points} pts)
            </button>
          )}
          {highlights.nightmare_team && (
            <button
              onClick={() => setShowTeam(showTeam === "nightmare" ? null : "nightmare")}
              className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                showTeam === "nightmare"
                  ? "border-red-500 bg-red-500/20 text-red-400"
                  : "border-vpv-border bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              <span aria-hidden="true">{"\uD83D\uDCC9"}</span>
              Peor XI ({highlights.nightmare_team.total_points} pts)
            </button>
          )}
        </div>
      )}

      {/* Dream/Nightmare team display */}
      {showTeam === "dream" && highlights.dream_team && (
        <TeamXI team={highlights.dream_team} variant="dream" />
      )}
      {showTeam === "nightmare" && highlights.nightmare_team && (
        <TeamXI team={highlights.nightmare_team} variant="nightmare" />
      )}
    </div>
  );
}

function TeamXI({
  team,
  variant,
}: {
  team: DreamTeamResponse;
  variant: "dream" | "nightmare";
}) {
  const borderColor =
    variant === "dream" ? "border-amber-500/30" : "border-red-500/30";
  const posOrder = ["POR", "DEF", "MED", "DEL"];

  const grouped = new Map<string, typeof team.players>();
  for (const p of team.players) {
    const list = grouped.get(p.position) ?? [];
    list.push(p);
    grouped.set(p.position, list);
  }

  return (
    <div className={`rounded-lg border ${borderColor} bg-vpv-card p-4`}>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold text-vpv-text-muted">
          {variant === "dream" ? "Mejor XI" : "Peor XI"} &middot;{" "}
          {team.formation}
        </p>
        <p className="text-sm font-bold text-vpv-text">
          {team.total_points} pts
        </p>
      </div>
      <div className="space-y-2">
        {posOrder.map((pos) => {
          const players = grouped.get(pos);
          if (!players) return null;
          return (
            <div key={pos} className="flex flex-wrap gap-2">
              {players.map((p) => (
                <div
                  key={p.player_id}
                  className="flex items-center gap-1.5 rounded-md bg-vpv-bg px-2 py-1.5"
                >
                  <PlayerAvatar
                    photoPath={p.photo_path}
                    name={p.player_name}
                    size={24}
                  />
                  <span
                    className={`rounded px-1 py-0.5 text-[9px] font-bold ${POSITION_COLORS[p.position] ?? ""}`}
                  >
                    {p.position}
                  </span>
                  <span className="text-xs text-vpv-text">{p.player_name}</span>
                  <span className="text-[10px] font-semibold tabular-nums text-vpv-accent">
                    {p.points}
                  </span>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
