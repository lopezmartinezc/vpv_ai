"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { EvolutionEntry } from "@/types";

interface PersonalEvolutionProps {
  entries: EvolutionEntry[];
  displayName: string;
}

export function PersonalEvolution({
  entries,
  displayName,
}: PersonalEvolutionProps) {
  const { chartData, stats, maxRank } = useMemo(() => {
    // Get all unique matchdays
    const matchdays = [
      ...new Set(entries.map((e) => e.matchday_number)),
    ].sort((a, b) => a - b);

    const totalParticipants = new Set(entries.map((e) => e.participant_id)).size;

    // Build chart data: per matchday, compute rank for all participants
    const data = matchdays.map((md) => {
      const mdEntries = entries.filter((e) => e.matchday_number === md);
      mdEntries.sort((a, b) => b.cumulative - a.cumulative);

      const myEntry = mdEntries.find((e) => e.display_name === displayName);
      const myRank = myEntry
        ? mdEntries.findIndex((e) => e.participant_id === myEntry.participant_id) + 1
        : null;

      return {
        matchday: md,
        points: myEntry?.points ?? 0,
        cumulative: myEntry?.cumulative ?? 0,
        rank: myRank,
      };
    });

    // Compute stats
    const myData = data.filter((d) => d.rank !== null);
    const bestMd = myData.reduce(
      (best, d) => (d.points > best.points ? d : best),
      myData[0],
    );
    const worstMd = myData.reduce(
      (worst, d) => (d.points < worst.points ? d : worst),
      myData[0],
    );
    const avgRank =
      myData.length > 0
        ? myData.reduce((sum, d) => sum + (d.rank ?? 0), 0) / myData.length
        : 0;
    const avgPoints =
      myData.length > 0
        ? myData.reduce((sum, d) => sum + d.points, 0) / myData.length
        : 0;

    // Best streak in top 3
    let bestStreak = 0;
    let currentStreak = 0;
    let streakStart = 0;
    let bestStreakStart = 0;
    for (let i = 0; i < myData.length; i++) {
      if ((myData[i].rank ?? 99) <= 3) {
        if (currentStreak === 0) streakStart = i;
        currentStreak++;
        if (currentStreak > bestStreak) {
          bestStreak = currentStreak;
          bestStreakStart = streakStart;
        }
      } else {
        currentStreak = 0;
      }
    }
    const streakRange =
      bestStreak > 0
        ? `J${myData[bestStreakStart].matchday}-J${myData[bestStreakStart + bestStreak - 1].matchday}`
        : null;

    return {
      chartData: data,
      stats: {
        bestMd,
        worstMd,
        avgRank: avgRank.toFixed(1),
        avgPoints: avgPoints.toFixed(1),
        bestStreak,
        streakRange,
        totalMatchdays: myData.length,
      },
      maxRank: totalParticipants,
    };
  }, [entries, displayName]);

  if (chartData.length === 0) return null;

  return (
    <div className="space-y-4">
      {/* Charts */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Points per matchday */}
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
            Puntos por jornada
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis
                  dataKey="matchday"
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  tickFormatter={(v: number) => `${v}`}
                  stroke="#374151"
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  stroke="#374151"
                  width={28}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1f2937",
                    border: "1px solid #374151",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  labelFormatter={(v) => `Jornada ${v}`}
                  formatter={(value: number) => [`${value} pts`, "Puntos"]}
                />
                <ReferenceLine
                  y={Number(stats.avgPoints)}
                  stroke="#6b7280"
                  strokeDasharray="3 3"
                  label={{
                    value: `Media: ${stats.avgPoints}`,
                    position: "right",
                    fill: "#6b7280",
                    fontSize: 10,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="points"
                  stroke="#f97316"
                  strokeWidth={2}
                  dot={{ r: 2, fill: "#f97316" }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Ranking evolution */}
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
            Posicion en la liga
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis
                  dataKey="matchday"
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  tickFormatter={(v: number) => `${v}`}
                  stroke="#374151"
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  stroke="#374151"
                  width={28}
                  reversed
                  domain={[1, maxRank]}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1f2937",
                    border: "1px solid #374151",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  labelFormatter={(v) => `Jornada ${v}`}
                  formatter={(value: number) => [`${value}\u00BA`, "Posicion"]}
                />
                <Line
                  type="monotone"
                  dataKey="rank"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 2, fill: "#3b82f6" }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {stats.bestMd && (
          <StatCard
            label="Mejor jornada"
            value={`${stats.bestMd.points} pts`}
            detail={`J${stats.bestMd.matchday} (#${stats.bestMd.rank})`}
            color="text-green-400"
          />
        )}
        {stats.worstMd && (
          <StatCard
            label="Peor jornada"
            value={`${stats.worstMd.points} pts`}
            detail={`J${stats.worstMd.matchday} (#${stats.worstMd.rank})`}
            color="text-red-400"
          />
        )}
        <StatCard
          label="Posicion media"
          value={`${stats.avgRank}\u00BA`}
          detail={`${stats.totalMatchdays} jornadas`}
          color="text-blue-400"
        />
        {stats.bestStreak > 0 && (
          <StatCard
            label="Mejor racha top 3"
            value={`${stats.bestStreak} jornadas`}
            detail={stats.streakRange ?? ""}
            color="text-amber-400"
          />
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  detail,
  color,
}: {
  label: string;
  value: string;
  detail: string;
  color: string;
}) {
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
        {label}
      </p>
      <p className={`text-lg font-bold tabular-nums ${color}`}>{value}</p>
      <p className="text-[10px] text-vpv-text-muted">{detail}</p>
    </div>
  );
}
