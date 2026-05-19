"use client";

import { useSeason } from "@/contexts/season-context";
import type { SeasonSummary } from "@/types";

function seasonLabel(s: SeasonSummary): string {
  const icon = s.kind === "tournament" ? "🏆" : "⚽";
  const tag = s.status === "active" ? " (actual)" : "";
  return `${icon} ${s.name}${tag}`;
}

export function SeasonSelector() {
  const { seasons, selectedSeason, selectSeason, loading } = useSeason();

  if (loading || !selectedSeason) return null;

  // Group seasons by kind, tournaments first then leagues, each group sorted by id desc
  const tournaments = seasons.filter((s) => s.kind === "tournament");
  const leagues = seasons.filter((s) => (s.kind ?? "league") === "league");

  return (
    <select
      value={selectedSeason.id}
      onChange={(e) => selectSeason(Number(e.target.value))}
      className="rounded-md border border-vpv-border bg-vpv-card px-3 py-1.5 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
    >
      {tournaments.length > 0 && (
        <optgroup label="🏆 Torneos">
          {tournaments.map((s) => (
            <option key={s.id} value={s.id}>
              {seasonLabel(s)}
            </option>
          ))}
        </optgroup>
      )}
      <optgroup label="⚽ Liga">
        {leagues.map((s) => (
          <option key={s.id} value={s.id}>
            {seasonLabel(s)}
          </option>
        ))}
      </optgroup>
    </select>
  );
}
