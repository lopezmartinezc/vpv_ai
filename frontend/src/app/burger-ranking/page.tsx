"use client";

import { useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import type { BurgerRankingResponse, BurgerEntry, BurgerGoal } from "@/types";
import { SkeletonCards } from "@/components/ui/skeleton";

export default function BurgerRankingPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading, error } = useFetch<BurgerRankingResponse>(
    selectedSeason ? `/burger-ranking/${selectedSeason.id}` : null,
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
        <p className="text-vpv-text-muted">No se pudo cargar el ranking</p>
      </div>
    );
  }

  const hasAnyBurger = data.entries.some((e) => e.total > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-vpv-text">🍔 Burger Ranking</h1>
        <p className="mt-1 text-sm text-vpv-text-muted">
          Goles de tus jugadores que se quedaron en el banquillo. Una
          hamburguesa por cada gol perdido.
        </p>
      </div>

      {!hasAnyBurger ? (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
          <p className="text-vpv-text-muted">Aún no hay hamburguesas servidas.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-vpv-card-border bg-vpv-card">
          <ul className="divide-y divide-vpv-border">
            {data.entries.map((entry, idx) => (
              <RankRow key={entry.participant_id} entry={entry} rank={idx + 1} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function RankRow({ entry, rank }: { entry: BurgerEntry; rank: number }) {
  const [open, setOpen] = useState(false);
  const isLeader = rank === 1 && entry.total > 0;
  const hasGoals = entry.goals.length > 0;

  return (
    <li className={open ? "bg-vpv-bg/40" : ""}>
      <button
        type="button"
        onClick={() => hasGoals && setOpen((p) => !p)}
        disabled={!hasGoals}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-vpv-bg/60 disabled:cursor-default disabled:opacity-70 disabled:hover:bg-transparent"
      >
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            isLeader
              ? "bg-vpv-gold text-black"
              : "bg-vpv-border text-vpv-text-muted"
          }`}
        >
          {rank}
        </span>
        <span
          className={`min-w-0 flex-1 truncate font-medium ${
            isLeader ? "text-vpv-accent" : "text-vpv-text"
          }`}
        >
          {entry.display_name}
        </span>
        <span className="font-mono text-sm tabular-nums text-vpv-text-muted">
          {"🍔".repeat(Math.min(entry.total, 5))}
          {entry.total > 5 && <span> +{entry.total - 5}</span>}
        </span>
        <span className="min-w-[2.5rem] text-right text-lg font-bold tabular-nums text-vpv-text">
          {entry.total}
        </span>
        {hasGoals && (
          <svg
            className={`h-4 w-4 text-vpv-text-muted transition-transform duration-200 ${
              open ? "rotate-180" : ""
            }`}
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
              clipRule="evenodd"
            />
          </svg>
        )}
      </button>

      {open && hasGoals && <Detail goals={entry.goals} />}
    </li>
  );
}

function Detail({ goals }: { goals: BurgerGoal[] }) {
  // Group by matchday for readability.
  const byMatchday = new Map<number, BurgerGoal[]>();
  for (const g of goals) {
    const list = byMatchday.get(g.matchday_number) ?? [];
    list.push(g);
    byMatchday.set(g.matchday_number, list);
  }
  const ordered = [...byMatchday.entries()].sort((a, b) => a[0] - b[0]);

  return (
    <div className="space-y-2 border-t border-vpv-border bg-vpv-bg/30 px-4 py-3 text-sm">
      {ordered.map(([md, list]) => (
        <div key={md}>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
            Jornada {md}
          </p>
          <ul className="mt-1 space-y-1">
            {list.map((g, i) => (
              <li
                key={`${g.player_id}-${i}`}
                className="flex items-center justify-between gap-2 rounded bg-vpv-card/60 px-2 py-1"
              >
                <span className="truncate text-vpv-text">
                  {g.player_name}
                  <span className="text-vpv-text-muted"> · {g.team_name}</span>
                </span>
                <span className="font-mono tabular-nums text-vpv-text-muted">
                  {"🍔".repeat(g.goals)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
