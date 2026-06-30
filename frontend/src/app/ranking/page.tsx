"use client";

import { useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SkeletonCards } from "@/components/ui/skeleton";
import type {
  BenchedPlayer,
  BenchEntry,
  BurgerEntry,
  BurgerGoal,
  RankingsResponse,
  SurvivorEntry,
  SurvivorPlayer,
} from "@/types";

type Tab = "burger" | "bench" | "survivors";

const TAB_CONFIG: Record<Tab, { label: string; emoji: string; subtitle: string; emptyMsg: string }> =
  {
    burger: {
      label: "Burger",
      emoji: "🍔",
      subtitle: "Goles de tus jugadores que se quedaron en el banquillo.",
      emptyMsg: "Aún no hay hamburguesas servidas.",
    },
    bench: {
      label: "Banquillazo",
      emoji: "🪑",
      subtitle: "Jugadores que pusiste en el XI pero no jugaron ni un minuto.",
      emptyMsg: "Aún no hay banquillazos registrados.",
    },
    survivors: {
      label: "Supervivientes",
      emoji: "🛡️",
      subtitle: "Cuántos de tus jugadores siguen vivos en el torneo.",
      emptyMsg: "Aún no hay jugadores en plantilla.",
    },
  };

export default function RankingPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading, error } = useFetch<RankingsResponse>(
    selectedSeason ? `/rankings/${selectedSeason.id}` : null,
  );
  const [tab, setTab] = useState<Tab>("burger");

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

  // Survivors only applies to tournaments (the API sends it as null for leagues).
  const survivors = data.survivors ?? null;
  const availableTabs: Tab[] = survivors
    ? ["burger", "bench", "survivors"]
    : ["burger", "bench"];
  const activeTab: Tab = availableTabs.includes(tab) ? tab : "burger";
  const cfg = TAB_CONFIG[activeTab];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-vpv-text">🏆 Ranking</h1>
        <p className="mt-1 text-sm text-vpv-text-muted">{cfg.subtitle}</p>
      </div>

      <div
        role="tablist"
        aria-label="Ranking"
        className="inline-flex rounded-lg border border-vpv-card-border bg-vpv-card p-1"
      >
        {availableTabs.map((key) => {
          const isActive = key === activeTab;
          const opt = TAB_CONFIG[key];
          return (
            <button
              key={key}
              role="tab"
              type="button"
              aria-selected={isActive}
              onClick={() => setTab(key)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-vpv-bg/80 text-vpv-text shadow-inner"
                  : "text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              <span className="mr-1.5">{opt.emoji}</span>
              {opt.label}
            </button>
          );
        })}
      </div>

      {activeTab === "burger" && (
        <BurgerSection entries={data.burger.entries} emptyMsg={TAB_CONFIG.burger.emptyMsg} />
      )}
      {activeTab === "bench" && (
        <BenchSection entries={data.bench.entries} emptyMsg={TAB_CONFIG.bench.emptyMsg} />
      )}
      {activeTab === "survivors" && survivors && (
        <SurvivorsSection
          entries={survivors.entries}
          groupStageDone={survivors.group_stage_done}
          emptyMsg={TAB_CONFIG.survivors.emptyMsg}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Burger section (reused styling from the old /burger-ranking page).
// ---------------------------------------------------------------------------

function BurgerSection({ entries, emptyMsg }: { entries: BurgerEntry[]; emptyMsg: string }) {
  const hasAny = entries.some((e) => e.total > 0);
  if (!hasAny) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">{emptyMsg}</p>
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border border-vpv-card-border bg-vpv-card">
      <ul className="divide-y divide-vpv-border">
        {entries.map((entry, idx) => (
          <BurgerRow key={entry.participant_id} entry={entry} rank={idx + 1} />
        ))}
      </ul>
    </div>
  );
}

function BurgerRow({ entry, rank }: { entry: BurgerEntry; rank: number }) {
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
        <RankBadge rank={rank} highlight={isLeader} />
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
        <Total value={entry.total} />
        {hasGoals && <Chevron open={open} />}
      </button>
      {open && hasGoals && <BurgerDetail goals={entry.goals} />}
    </li>
  );
}

function BurgerDetail({ goals }: { goals: BurgerGoal[] }) {
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
          <MatchdayLabel md={md} />
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

// ---------------------------------------------------------------------------
// Bench section.
// ---------------------------------------------------------------------------

function BenchSection({ entries, emptyMsg }: { entries: BenchEntry[]; emptyMsg: string }) {
  const hasAny = entries.some((e) => e.total > 0);
  if (!hasAny) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">{emptyMsg}</p>
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border border-vpv-card-border bg-vpv-card">
      <ul className="divide-y divide-vpv-border">
        {entries.map((entry, idx) => (
          <BenchRow key={entry.participant_id} entry={entry} rank={idx + 1} />
        ))}
      </ul>
    </div>
  );
}

function BenchRow({ entry, rank }: { entry: BenchEntry; rank: number }) {
  const [open, setOpen] = useState(false);
  const isLeader = rank === 1 && entry.total > 0;
  const hasPlayers = entry.players.length > 0;
  return (
    <li className={open ? "bg-vpv-bg/40" : ""}>
      <button
        type="button"
        onClick={() => hasPlayers && setOpen((p) => !p)}
        disabled={!hasPlayers}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-vpv-bg/60 disabled:cursor-default disabled:opacity-70 disabled:hover:bg-transparent"
      >
        <RankBadge rank={rank} highlight={isLeader} />
        <span
          className={`min-w-0 flex-1 truncate font-medium ${
            isLeader ? "text-vpv-accent" : "text-vpv-text"
          }`}
        >
          {entry.display_name}
        </span>
        <span className="font-mono text-sm tabular-nums text-vpv-text-muted">
          {"🪑".repeat(Math.min(entry.total, 5))}
          {entry.total > 5 && <span> +{entry.total - 5}</span>}
        </span>
        <Total value={entry.total} />
        {hasPlayers && <Chevron open={open} />}
      </button>
      {open && hasPlayers && <BenchDetail players={entry.players} />}
    </li>
  );
}

function BenchDetail({ players }: { players: BenchedPlayer[] }) {
  const byMatchday = new Map<number, BenchedPlayer[]>();
  for (const p of players) {
    const list = byMatchday.get(p.matchday_number) ?? [];
    list.push(p);
    byMatchday.set(p.matchday_number, list);
  }
  const ordered = [...byMatchday.entries()].sort((a, b) => a[0] - b[0]);
  return (
    <div className="space-y-2 border-t border-vpv-border bg-vpv-bg/30 px-4 py-3 text-sm">
      {ordered.map(([md, list]) => (
        <div key={md}>
          <MatchdayLabel md={md} />
          <ul className="mt-1 space-y-1">
            {list.map((p, i) => (
              <li
                key={`${p.player_id}-${i}`}
                className="flex items-center justify-between gap-2 rounded bg-vpv-card/60 px-2 py-1"
              >
                <span className="truncate text-vpv-text">
                  <span className="mr-1 inline-block w-7 text-[10px] font-mono text-vpv-text-muted">
                    {p.position || "—"}
                  </span>
                  {p.player_name}
                  <span className="text-vpv-text-muted"> · {p.team_name}</span>
                </span>
                <span className="font-mono tabular-nums text-vpv-text-muted">🪑</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Survivors section (tournaments only).
// ---------------------------------------------------------------------------

function SurvivorsSection({
  entries,
  groupStageDone,
  emptyMsg,
}: {
  entries: SurvivorEntry[];
  groupStageDone: boolean;
  emptyMsg: string;
}) {
  const hasAny = entries.some((e) => e.total > 0);
  if (!hasAny) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">{emptyMsg}</p>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {!groupStageDone && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2 text-sm text-vpv-text-muted">
          La fase de grupos sigue en juego — nadie eliminado todavía.
        </div>
      )}
      <div className="overflow-hidden rounded-lg border border-vpv-card-border bg-vpv-card">
        <ul className="divide-y divide-vpv-border">
          {entries.map((entry, idx) => (
            <SurvivorRow key={entry.participant_id} entry={entry} rank={idx + 1} />
          ))}
        </ul>
      </div>
    </div>
  );
}

function SurvivorRow({ entry, rank }: { entry: SurvivorEntry; rank: number }) {
  const [open, setOpen] = useState(false);
  const isLeader = rank === 1 && entry.total > 0;
  const hasPlayers = entry.players.length > 0;
  const pct = entry.total > 0 ? Math.round((entry.alive_count / entry.total) * 100) : 0;
  return (
    <li className={open ? "bg-vpv-bg/40" : ""}>
      <button
        type="button"
        onClick={() => hasPlayers && setOpen((p) => !p)}
        disabled={!hasPlayers}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-vpv-bg/60 disabled:cursor-default disabled:opacity-70 disabled:hover:bg-transparent"
      >
        <RankBadge rank={rank} highlight={isLeader} />
        <div className="min-w-0 flex-1">
          <span
            className={`block truncate font-medium ${
              isLeader ? "text-vpv-accent" : "text-vpv-text"
            }`}
          >
            {entry.display_name}
          </span>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-vpv-border">
            <div className="h-full rounded-full bg-green-500/70" style={{ width: `${pct}%` }} />
          </div>
        </div>
        <span className="shrink-0 font-mono text-sm tabular-nums text-vpv-text-muted">
          <span className="text-green-400">{entry.alive_count}</span>
          <span className="mx-1">/</span>
          <span className="text-vpv-text-muted">{entry.total}</span>
        </span>
        {hasPlayers && <Chevron open={open} />}
      </button>
      {open && hasPlayers && <SurvivorDetail players={entry.players} />}
    </li>
  );
}

function SurvivorDetail({ players }: { players: SurvivorPlayer[] }) {
  return (
    <div className="border-t border-vpv-border bg-vpv-bg/30 px-4 py-3 text-sm">
      <ul className="space-y-1">
        {players.map((p) => (
          <li
            key={p.player_id}
            className={`flex items-center justify-between gap-2 rounded px-2 py-1 ${
              p.alive ? "bg-vpv-card/60" : "bg-vpv-card/30 opacity-60"
            }`}
          >
            <span className="min-w-0 truncate text-vpv-text">
              <span className="mr-1 inline-block w-7 text-[10px] font-mono text-vpv-text-muted">
                {p.position || "—"}
              </span>
              <span className={p.alive ? "" : "line-through"}>{p.player_name}</span>
              <span className="text-vpv-text-muted"> · {p.team_name}</span>
            </span>
            <span className="shrink-0 font-mono tabular-nums">
              {p.alive ? "🟢" : "⚰️"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared row pieces.
// ---------------------------------------------------------------------------

function RankBadge({ rank, highlight }: { rank: number; highlight: boolean }) {
  return (
    <span
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
        highlight ? "bg-vpv-gold text-black" : "bg-vpv-border text-vpv-text-muted"
      }`}
    >
      {rank}
    </span>
  );
}

function Total({ value }: { value: number }) {
  return (
    <span className="min-w-[2.5rem] text-right text-lg font-bold tabular-nums text-vpv-text">
      {value}
    </span>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
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
  );
}

function MatchdayLabel({ md }: { md: number }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
      Jornada {md}
    </p>
  );
}
