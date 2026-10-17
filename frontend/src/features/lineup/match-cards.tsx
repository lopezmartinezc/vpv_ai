"use client";

import { useMemo, useState, type JSX } from "react";
import { POSITION_COLORS, type Position } from "@/features/lineup/positions";
import type { MatchEntry, SquadPlayerEntry } from "@/types";

export function formatMatchTime(playedAt: string | null): string {
  if (!playedAt) return "";
  const d = new Date(playedAt);
  const day = d.toLocaleDateString("es-ES", { weekday: "short" });
  const time = d.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${day} ${time}`;
}

export function MatchCards({
  matches,
  squad,
  selectedIds,
}: {
  matches: MatchEntry[];
  squad: SquadPlayerEntry[];
  selectedIds: Set<number>;
}): JSX.Element | null {
  const [open, setOpen] = useState(false);

  const squadByTeam = useMemo(() => {
    const map = new Map<string, SquadPlayerEntry[]>();
    for (const p of squad) {
      const list = map.get(p.team_name) ?? [];
      list.push(p);
      map.set(p.team_name, list);
    }
    return map;
  }, [squad]);

  if (matches.length === 0) return null;

  return (
    <div className="rounded-lg border border-vpv-border bg-vpv-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2.5"
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
          Partidos ({matches.length})
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          className={`text-vpv-text-muted transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path
            d="M3.5 5.5l3.5 3.5 3.5-3.5"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div className="divide-y divide-vpv-border/50 border-t border-vpv-border">
          {matches.map((m) => {
            const homePlayers = squadByTeam.get(m.home_team) ?? [];
            const awayPlayers = squadByTeam.get(m.away_team) ?? [];
            const hasPlayers =
              homePlayers.length > 0 || awayPlayers.length > 0;

            return (
              <div key={m.id} className="px-3 py-2">
                {/* Match header */}
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-vpv-text">
                    {m.home_team} - {m.away_team}
                  </span>
                  {m.played_at && (
                    <span className="text-xs text-vpv-text-muted">
                      {formatMatchTime(m.played_at)}
                    </span>
                  )}
                </div>

                {/* Squad players per team */}
                {hasPlayers && (
                  <div className="mt-1.5 grid grid-cols-2 gap-x-3">
                    <SquadColumn
                      players={homePlayers}
                      selectedIds={selectedIds}
                    />
                    <SquadColumn
                      players={awayPlayers}
                      selectedIds={selectedIds}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SquadColumn({
  players,
  selectedIds,
}: {
  players: SquadPlayerEntry[];
  selectedIds: Set<number>;
}): JSX.Element {
  if (players.length === 0) return <div />;

  return (
    <div className="space-y-0.5">
      {players.map((p) => {
        const selected = selectedIds.has(p.player_id);
        const pos = p.position as Position;
        return (
          <div key={p.player_id} className="flex items-center gap-1.5">
            <span
              className={`rounded px-1 py-px text-[9px] font-bold ${POSITION_COLORS[pos]}`}
            >
              {pos}
            </span>
            <span
              className={`truncate text-xs ${
                selected
                  ? "font-semibold text-vpv-accent"
                  : "text-vpv-text-muted"
              }`}
            >
              {p.display_name}
            </span>
          </div>
        );
      })}
    </div>
  );
}
