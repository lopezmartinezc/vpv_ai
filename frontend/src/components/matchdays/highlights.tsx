"use client";

import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { HighlightPlayer } from "@/types";

const HIGHLIGHT_CARDS: {
  key: string;
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
  highlights: Record<string, HighlightPlayer | null>;
}) {
  const cards = HIGHLIGHT_CARDS.filter((c) => highlights[c.key] != null);
  if (cards.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {cards.map((card) => {
        const player = highlights[card.key]!;
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
  );
}
