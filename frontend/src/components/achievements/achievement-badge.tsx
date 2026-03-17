"use client";

import type { AchievementEntry } from "@/types";

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

const TIER_COLORS = [
  "bg-amber-700/30 text-amber-500",     // tier 1 (bronze)
  "bg-gray-400/20 text-gray-300",        // tier 2 (silver)
  "bg-yellow-500/20 text-yellow-400",    // tier 3 (gold)
];

const TIER_LABELS: Record<string, Record<number, string>> = {
  racha_ganadora: { 1: "3 jornadas", 2: "5 jornadas", 3: "7 jornadas" },
  racha_perdedora: { 1: "3 jornadas", 2: "5 jornadas", 3: "7 jornadas" },
  imbatible: { 1: "2 jornadas", 2: "3 jornadas", 3: "5 jornadas" },
};

export function AchievementBadge({ achievement }: { achievement: AchievementEntry }) {
  const tierColor = TIER_COLORS[Math.min(achievement.tier - 1, 2)];
  const tierLabel = TIER_LABELS[achievement.achievement_key]?.[achievement.tier];

  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${tierColor}`}
      title={`${achievement.description}${tierLabel ? ` (${tierLabel})` : ""}`}
    >
      <span className="text-sm">{ICON_MAP[achievement.icon] ?? achievement.icon}</span>
      <span>{achievement.name}</span>
      {achievement.tier > 1 && (
        <span className="text-[10px] opacity-70">x{achievement.tier}</span>
      )}
    </div>
  );
}

export function AchievementList({ achievements }: { achievements: AchievementEntry[] }) {
  if (achievements.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {achievements.map((a) => (
        <AchievementBadge key={a.id} achievement={a} />
      ))}
    </div>
  );
}
