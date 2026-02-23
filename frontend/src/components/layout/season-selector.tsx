"use client";

import { useSeason } from "@/contexts/season-context";

export function SeasonSelector() {
  const { seasons, selectedSeason, selectSeason, loading } = useSeason();

  if (loading || !selectedSeason) return null;

  return (
    <select
      value={selectedSeason.id}
      onChange={(e) => selectSeason(Number(e.target.value))}
      className="rounded-md border border-vpv-border bg-vpv-card px-3 py-1.5 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
    >
      {seasons.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name}
          {s.status === "active" ? " (actual)" : ""}
        </option>
      ))}
    </select>
  );
}
