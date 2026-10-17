"use client";

import type { JSX } from "react";
import { POSITION_ORDER, type Position } from "@/features/lineup/positions";

export function PositionTabs({
  activeTab,
  onTabChange,
  counts,
  canAdd,
}: {
  activeTab: Position;
  onTabChange: (pos: Position) => void;
  counts: Record<Position, number>;
  canAdd: Record<Position, boolean>;
}): JSX.Element {
  return (
    <div
      className="flex rounded-xl bg-vpv-bg p-1"
      role="tablist"
      aria-label="Posiciones"
    >
      {POSITION_ORDER.map((pos) => {
        const active = pos === activeTab;
        const full = !canAdd[pos] && counts[pos] > 0;
        return (
          <button
            key={pos}
            role="tab"
            aria-selected={active}
            onClick={() => onTabChange(pos)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-medium transition-all ${
              active
                ? "bg-vpv-card text-vpv-text shadow-sm"
                : "text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            <span>{pos}</span>
            {counts[pos] > 0 && (
              <span
                className={`min-w-[18px] rounded-full px-1 text-center text-[11px] font-bold ${
                  full
                    ? "bg-vpv-success/20 text-vpv-success"
                    : "bg-vpv-accent/20 text-vpv-accent"
                }`}
              >
                {counts[pos]}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
