"use client";

import { useMemo, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { SeasonSelector } from "@/components/layout/season-selector";
import type { AchievementEntry, SeasonAchievementsResponse } from "@/types";

const ICON_MAP: Record<string, string> = {
  star: "\u2B50",
  goal: "\u26BD",
  shield: "\uD83D\uDEE1\uFE0F",
  fire: "\uD83D\uDD25",
  ice: "\u2744\uFE0F",
  crown: "\uD83D\uDC51",
  chart: "\uD83D\uDCC8",
  target: "\uD83C\uDFAF",
};

const ACHIEVEMENT_ORDER = [
  "mvp_jornada",
  "goleador",
  "muro",
  "racha_ganadora",
  "racha_perdedora",
  "imbatible",
  "lider",
  "robo_draft",
];

type ViewMode = "ranking" | "timeline";

export default function LogrosPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const { data, loading } = useFetch<SeasonAchievementsResponse>(
    selectedSeason ? `/achievements/${selectedSeason.id}` : null,
  );
  const [view, setView] = useState<ViewMode>("ranking");
  const [expandedParticipant, setExpandedParticipant] = useState<number | null>(null);

  // Achievement definitions from the data
  const achievementTypes = useMemo(() => {
    if (!data) return [];
    const seen = new Map<string, { key: string; name: string; icon: string }>();
    for (const a of data.achievements) {
      if (!seen.has(a.achievement_key)) {
        seen.set(a.achievement_key, { key: a.achievement_key, name: a.name, icon: a.icon });
      }
    }
    return ACHIEVEMENT_ORDER
      .filter((k) => seen.has(k))
      .map((k) => seen.get(k)!);
  }, [data]);

  // Ranking data: participant -> count per achievement type + total
  const rankingData = useMemo(() => {
    if (!data) return [];
    const map = new Map<number, {
      name: string;
      total: number;
      counts: Record<string, number>;
      achievements: AchievementEntry[];
    }>();

    for (const a of data.achievements) {
      const existing = map.get(a.participant_id);
      if (existing) {
        existing.total++;
        existing.counts[a.achievement_key] = (existing.counts[a.achievement_key] || 0) + 1;
        existing.achievements.push(a);
      } else {
        map.set(a.participant_id, {
          name: a.display_name,
          total: 1,
          counts: { [a.achievement_key]: 1 },
          achievements: [a],
        });
      }
    }

    return [...map.entries()]
      .map(([id, d]) => ({ id, ...d }))
      .sort((a, b) => b.total - a.total);
  }, [data]);

  // Timeline data: grouped by matchday
  const timelineData = useMemo(() => {
    if (!data) return [];
    const map = new Map<number, AchievementEntry[]>();
    for (const a of data.achievements) {
      if (a.matchday_number == null) continue;
      const list = map.get(a.matchday_number) ?? [];
      list.push(a);
      map.set(a.matchday_number, list);
    }
    return [...map.entries()]
      .sort(([a], [b]) => b - a)
      .map(([number, achievements]) => ({ number, achievements }));
  }, [data]);

  if (seasonLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />
        <div className="h-64 animate-pulse rounded-lg bg-vpv-border" />
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
          No hay logros registrados. Ejecuta la evaluacion desde el endpoint admin.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-vpv-text">
          Logros ({data.achievements.length})
        </h1>
        <SeasonSelector />
      </div>

      {/* View toggle */}
      <div className="flex gap-1">
        <button
          onClick={() => setView("ranking")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
            view === "ranking"
              ? "bg-vpv-accent text-white"
              : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
          }`}
        >
          Ranking
        </button>
        <button
          onClick={() => setView("timeline")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
            view === "timeline"
              ? "bg-vpv-accent text-white"
              : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
          }`}
        >
          Por jornada
        </button>
      </div>

      {/* Ranking view */}
      {view === "ranking" && (
        <div className="overflow-x-auto rounded-lg border border-vpv-card-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-vpv-border bg-vpv-card text-left text-xs text-vpv-text-muted">
                <th className="w-8 px-3 py-2.5 text-center">#</th>
                <th className="px-3 py-2.5">Participante</th>
                {achievementTypes.map((t) => (
                  <th
                    key={t.key}
                    className="w-12 px-2 py-2.5 text-center"
                    title={t.name}
                  >
                    {ICON_MAP[t.icon] ?? t.icon}
                  </th>
                ))}
                <th className="w-14 px-3 py-2.5 text-center font-bold">Total</th>
              </tr>
            </thead>
            <tbody>
              {rankingData.map((row, i) => (
                <>
                  <tr
                    key={row.id}
                    onClick={() =>
                      setExpandedParticipant(
                        expandedParticipant === row.id ? null : row.id,
                      )
                    }
                    className="cursor-pointer border-b border-vpv-border last:border-0 hover:bg-vpv-accent/5"
                  >
                    <td className="px-3 py-2.5 text-center tabular-nums text-vpv-text-muted">
                      {i + 1}
                    </td>
                    <td className="px-3 py-2.5 font-medium text-vpv-text">
                      {row.name}
                    </td>
                    {achievementTypes.map((t) => {
                      const count = row.counts[t.key] || 0;
                      return (
                        <td
                          key={t.key}
                          className="px-2 py-2.5 text-center tabular-nums"
                        >
                          {count > 0 ? (
                            <span className="text-vpv-text">{count}</span>
                          ) : (
                            <span className="text-vpv-text-muted/30">-</span>
                          )}
                        </td>
                      );
                    })}
                    <td className="px-3 py-2.5 text-center font-bold tabular-nums text-vpv-accent">
                      {row.total}
                    </td>
                  </tr>
                  {expandedParticipant === row.id && (
                    <tr key={`${row.id}-detail`}>
                      <td
                        colSpan={achievementTypes.length + 3}
                        className="border-b border-vpv-border bg-vpv-bg/50 px-4 py-3"
                      >
                        <ParticipantDetail achievements={row.achievements} />
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Timeline view */}
      {view === "timeline" && (
        <div className="space-y-3">
          {timelineData.map(({ number, achievements }) => (
            <div
              key={number}
              className="rounded-lg border border-vpv-card-border bg-vpv-card p-4"
            >
              <h3 className="mb-2 text-sm font-semibold text-vpv-text-muted">
                Jornada {number}
              </h3>
              <div className="space-y-1.5">
                {achievements.map((a) => (
                  <div
                    key={a.id}
                    className="flex items-center gap-2 text-sm"
                  >
                    <span className="text-base">
                      {ICON_MAP[a.icon] ?? a.icon}
                    </span>
                    <span className="font-medium text-vpv-text">
                      {a.name}
                    </span>
                    <span className="text-vpv-text-muted">—</span>
                    <span className="text-vpv-text">{a.display_name}</span>
                    {a.tier > 1 && (
                      <span className="rounded bg-vpv-accent/20 px-1.5 py-0.5 text-[10px] font-bold text-vpv-accent">
                        x{a.tier}
                      </span>
                    )}
                    {a.metadata && (
                      <span className="text-xs text-vpv-text-muted/60">
                        {formatMetadata(a)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ParticipantDetail({ achievements }: { achievements: AchievementEntry[] }) {
  const sorted = [...achievements].sort(
    (a, b) => (a.matchday_number ?? 0) - (b.matchday_number ?? 0),
  );

  return (
    <div className="space-y-1">
      {sorted.map((a) => (
        <div key={a.id} className="flex items-center gap-2 text-xs">
          <span className="w-10 text-right tabular-nums text-vpv-text-muted">
            {a.matchday_number ? `J${a.matchday_number}` : ""}
          </span>
          <span>{ICON_MAP[a.icon] ?? a.icon}</span>
          <span className="font-medium text-vpv-text">{a.name}</span>
          {a.tier > 1 && (
            <span className="rounded bg-vpv-accent/20 px-1 py-0.5 text-[10px] font-bold text-vpv-accent">
              x{a.tier}
            </span>
          )}
          {a.metadata && (
            <span className="text-vpv-text-muted/60">{formatMetadata(a)}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function formatMetadata(a: AchievementEntry): string {
  const m = a.metadata;
  if (!m) return "";
  if (a.achievement_key === "mvp_jornada" && m.points) return `${m.points} pts`;
  if (a.achievement_key === "goleador" && m.goals) return `${m.goals} goles`;
  if (a.achievement_key === "muro" && m.pts_clean_sheet) return `${m.pts_clean_sheet} pts imb.`;
  if (a.achievement_key === "robo_draft" && m.round_number) return `R${m.round_number}`;
  if ((a.achievement_key === "racha_ganadora" || a.achievement_key === "racha_perdedora" || a.achievement_key === "imbatible") && m.streak) return `${m.streak} jornadas`;
  return "";
}
