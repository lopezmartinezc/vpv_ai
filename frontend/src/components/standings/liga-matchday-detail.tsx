"use client";

import { useState, useEffect } from "react";
import { useFetch } from "@/hooks/use-fetch";
import type { MatchdaySummaryItem, MatchdayDetailResponse } from "@/types";

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1)
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-vpv-gold text-[10px] font-bold text-black">
        1
      </span>
    );
  if (rank === 2)
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-gray-300 text-[10px] font-bold text-black">
        2
      </span>
    );
  if (rank === 3)
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-amber-700 text-[10px] font-bold text-white">
        3
      </span>
    );
  return (
    <span className="inline-flex h-6 w-6 items-center justify-center text-xs text-vpv-text-muted">
      {rank}
    </span>
  );
}

export function LigaMatchdayDetail({
  seasonId,
  matchdays,
  matchdayCurrent,
}: {
  seasonId: number;
  matchdays: MatchdaySummaryItem[];
  matchdayCurrent: number | null;
}) {
  const playedMatchdays = matchdays.filter((md) => md.stats_ok);

  const defaultMd =
    playedMatchdays.find((md) => md.number === matchdayCurrent)?.number ??
    playedMatchdays[playedMatchdays.length - 1]?.number;

  const [selected, setSelected] = useState<number>(defaultMd ?? 1);

  // Update selected when matchdayCurrent changes (season switch)
  useEffect(() => {
    if (defaultMd) setSelected(defaultMd);
  }, [defaultMd]);

  const { data, loading } = useFetch<MatchdayDetailResponse>(
    selected ? `/matchdays/${seasonId}/${selected}` : null,
  );

  if (playedMatchdays.length === 0) return null;

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Detalle por jornada
        </h2>
        <select
          value={selected}
          onChange={(e) => setSelected(Number(e.target.value))}
          className="rounded-md border border-vpv-border bg-vpv-card px-3 py-1.5 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
        >
          {[...playedMatchdays].reverse().map((md) => (
            <option key={md.number} value={md.number}>
              Jornada {md.number}
            </option>
          ))}
        </select>
      </div>

      <div className="px-4 pb-3">
        {loading && (
          <div className="space-y-2 py-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-7 animate-pulse rounded bg-vpv-border"
              />
            ))}
          </div>
        )}

        {!loading && data && data.scores.length > 0 && (
          <div className="divide-y divide-vpv-border/50">
            {data.scores.map((s, i) => (
              <div
                key={s.participant_id}
                className="flex items-center gap-2 py-1.5 text-sm"
              >
                <RankBadge rank={i + 1} />
                <span className="min-w-0 flex-1 truncate font-medium text-vpv-text">
                  {s.display_name}
                </span>
                {s.formation && (
                  <span className="hidden text-xs text-vpv-text-muted sm:inline">
                    {s.formation}
                  </span>
                )}
                <span
                  className={`w-10 text-right text-sm font-bold tabular-nums ${i === 0 ? "text-vpv-accent" : "text-vpv-text"}`}
                >
                  {s.total_points}
                </span>
              </div>
            ))}
          </div>
        )}

        {!loading && data && data.scores.length === 0 && (
          <p className="py-2 text-xs text-vpv-text-muted">
            Sin datos para esta jornada
          </p>
        )}
      </div>
    </div>
  );
}
