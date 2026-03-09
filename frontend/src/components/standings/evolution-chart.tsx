"use client";

import { useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface EvolutionEntry {
  matchday_number: number;
  participant_id: number;
  display_name: string;
  points: number;
  cumulative: number;
}

// 14 distinct colors for participants
const COLORS = [
  "#f97316", // orange
  "#3b82f6", // blue
  "#22c55e", // green
  "#ef4444", // red
  "#a855f7", // purple
  "#eab308", // yellow
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#14b8a6", // teal
  "#f59e0b", // amber
  "#6366f1", // indigo
  "#84cc16", // lime
  "#d946ef", // fuchsia
  "#64748b", // slate
];

export function EvolutionChart({
  entries,
}: {
  entries: EvolutionEntry[];
}) {
  const { chartData, participants, maxRank } = useMemo(() => {
    // Get unique participants preserving order
    const participantMap = new Map<number, string>();
    for (const e of entries) {
      if (!participantMap.has(e.participant_id)) {
        participantMap.set(e.participant_id, e.display_name);
      }
    }

    // Get unique matchday numbers
    const matchdays = [...new Set(entries.map((e) => e.matchday_number))].sort(
      (a, b) => a - b,
    );

    // Build cumulative per matchday, then derive ranking
    const data = matchdays.map((md) => {
      // Collect cumulative for each participant at this matchday
      const cumulatives: { name: string; cumulative: number }[] = [];
      for (const e of entries) {
        if (e.matchday_number === md) {
          cumulatives.push({ name: e.display_name, cumulative: e.cumulative });
        }
      }

      // Sort by cumulative desc to assign ranking (1 = best)
      cumulatives.sort((a, b) => b.cumulative - a.cumulative);

      const row: Record<string, number> = { matchday: md };
      cumulatives.forEach((c, idx) => {
        row[c.name] = idx + 1;
      });
      return row;
    });

    const n = participantMap.size;

    const parts = [...participantMap.entries()].map(([id, name], idx) => ({
      id,
      name,
      color: COLORS[idx % COLORS.length],
    }));

    return { chartData: data, participants: parts, maxRank: n };
  }, [entries]);

  // Toggle visibility per participant
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  function toggleParticipant(name: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  if (entries.length === 0) return null;

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
        Evolucion por jornada
      </h2>

      <div className="h-72 w-full sm:h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <XAxis
              dataKey="matchday"
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              tickFormatter={(v: number) => `J${v}`}
              stroke="#374151"
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              stroke="#374151"
              width={28}
              reversed
              domain={[1, maxRank]}
              tickCount={maxRank}
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
              formatter={(value, name) => [`${value}º`, name]}
              itemSorter="value"
            />
            {participants.map((p) => (
              <Line
                key={p.id}
                type="monotone"
                dataKey={p.name}
                stroke={p.color}
                strokeWidth={2}
                dot={false}
                hide={hidden.has(p.name)}
                activeDot={{ r: 4 }}
              />
            ))}
            <Legend content={() => null} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Custom legend with toggles */}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {participants.map((p) => {
          const isHidden = hidden.has(p.name);
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => toggleParticipant(p.name)}
              className={`flex items-center gap-1.5 text-xs transition-opacity ${
                isHidden ? "opacity-30" : ""
              }`}
            >
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: p.color }}
              />
              <span className="text-vpv-text">{p.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
