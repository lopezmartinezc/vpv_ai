"use client";

import { useMemo, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SeasonSelector } from "@/components/layout/season-selector";
import { AchievementBadge } from "@/components/achievements/achievement-badge";
import type { AchievementEntry, SeasonAchievementsResponse } from "@/types";

const CATEGORY_LABELS: Record<string, string> = {
  weekly: "Semanal",
  streak: "Racha",
  milestone: "Hito",
  draft: "Draft",
};

const CATEGORY_ORDER = ["weekly", "streak", "milestone", "draft"];

export default function LogrosPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<SeasonAchievementsResponse>(
    selectedSeason ? `/achievements/${selectedSeason.id}` : null,
  );

  const [filterCategory, setFilterCategory] = useState<string | null>(null);
  const [filterParticipant, setFilterParticipant] = useState<number | null>(null);

  // Group achievements by participant
  const byParticipant = useMemo(() => {
    if (!data) return new Map<number, { name: string; achievements: AchievementEntry[] }>();
    const map = new Map<number, { name: string; achievements: AchievementEntry[] }>();
    for (const a of data.achievements) {
      if (filterCategory && a.category !== filterCategory) continue;
      const existing = map.get(a.participant_id);
      if (existing) {
        existing.achievements.push(a);
      } else {
        map.set(a.participant_id, { name: a.display_name, achievements: [a] });
      }
    }
    return map;
  }, [data, filterCategory]);

  // Unique participants for filter
  const participants = useMemo(() => {
    if (!data) return [];
    const seen = new Map<number, string>();
    for (const a of data.achievements) {
      if (!seen.has(a.participant_id)) {
        seen.set(a.participant_id, a.display_name);
      }
    }
    return [...seen.entries()].map(([id, name]) => ({ id, name }));
  }, [data]);

  // Categories present
  const categories = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    for (const a of data.achievements) set.add(a.category);
    return CATEGORY_ORDER.filter((c) => set.has(c));
  }, [data]);

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg bg-vpv-border" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.achievements.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-vpv-text">Logros</h1>
          <SeasonSelector />
        </div>
        <p className="py-10 text-center text-vpv-text-muted">
          No hay logros registrados para esta temporada.
        </p>
      </div>
    );
  }

  const displayParticipants = filterParticipant
    ? [[filterParticipant, byParticipant.get(filterParticipant)] as const].filter(
        ([, v]) => v != null,
      )
    : [...byParticipant.entries()].sort(
        ([, a], [, b]) => b.achievements.length - a.achievements.length,
      );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">Logros</h1>
        <SeasonSelector />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {/* Category filter */}
        <div className="flex gap-1">
          <button
            onClick={() => setFilterCategory(null)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              filterCategory === null
                ? "bg-vpv-accent text-white"
                : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            Todos
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(filterCategory === cat ? null : cat)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                filterCategory === cat
                  ? "bg-vpv-accent text-white"
                  : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {CATEGORY_LABELS[cat] ?? cat}
            </button>
          ))}
        </div>

        {/* Participant filter */}
        {participants.length > 1 && (
          <select
            value={filterParticipant ?? ""}
            onChange={(e) => setFilterParticipant(e.target.value ? Number(e.target.value) : null)}
            className="rounded-lg border border-vpv-border bg-vpv-card px-3 py-1.5 text-xs text-vpv-text focus:border-vpv-accent focus:outline-none"
          >
            <option value="">Todos los participantes</option>
            {participants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Participant cards */}
      <div className="grid gap-4 sm:grid-cols-2">
        {displayParticipants.map(([pid, entry]) => {
          if (!entry) return null;
          return (
            <div
              key={pid}
              className="rounded-lg border border-vpv-card-border bg-vpv-card p-4"
            >
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-semibold text-vpv-text">{entry.name}</h3>
                <span className="rounded-full bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                  {entry.achievements.length}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {entry.achievements.map((a) => (
                  <AchievementBadge key={a.id} achievement={a} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
