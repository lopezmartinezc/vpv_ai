"use client";

import { useState } from "react";
import type { CopaMatchdayDetail } from "@/types";

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-4 w-4 text-vpv-text-muted transition-transform duration-200 ${open ? "rotate-180" : ""}`}
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

function ResultLabel({ points }: { points: number }) {
  if (points === 3)
    return (
      <span className="rounded bg-vpv-success/20 px-1.5 py-0.5 text-[10px] font-bold text-vpv-success">
        V
      </span>
    );
  if (points === 1)
    return (
      <span className="rounded bg-vpv-text-muted/20 px-1.5 py-0.5 text-[10px] font-bold text-vpv-text-muted">
        E
      </span>
    );
  return (
    <span className="rounded bg-vpv-danger/20 px-1.5 py-0.5 text-[10px] font-bold text-vpv-danger">
      D
    </span>
  );
}

function MatchdayRow({ matchday }: { matchday: CopaMatchdayDetail }) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className={`border-b border-vpv-border last:border-0 ${open ? "bg-vpv-bg/50" : ""}`}
    >
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-vpv-bg/80"
      >
        <span className="text-sm font-bold text-vpv-text">
          Jornada {matchday.matchday_number}
        </span>
        <span className="flex-1" />
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div className="px-4 pb-3">
          <div className="divide-y divide-vpv-border/50">
            {matchday.results.map((r) => (
              <div
                key={r.participant_id}
                className="flex items-center gap-2 py-1.5 text-sm"
              >
                <ResultLabel points={r.points} />
                <span className="min-w-0 flex-1 truncate font-medium text-vpv-text">
                  {r.display_name}
                </span>
                <span className="tabular-nums text-vpv-text">
                  {r.goals_for}-{r.goals_against}
                </span>
                <span
                  className={`w-8 text-right text-xs font-bold tabular-nums ${r.goal_difference > 0 ? "text-vpv-success" : r.goal_difference < 0 ? "text-vpv-danger" : "text-vpv-text-muted"}`}
                >
                  {r.goal_difference > 0
                    ? `+${r.goal_difference}`
                    : r.goal_difference}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function CopaMatchdays({
  matchdays,
}: {
  matchdays: CopaMatchdayDetail[];
}) {
  // Show most recent first
  const reversed = [...matchdays].reverse();

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Detalle por jornada
        </h2>
      </div>
      <div>
        {reversed.map((md) => (
          <MatchdayRow key={md.matchday_number} matchday={md} />
        ))}
      </div>
    </div>
  );
}
