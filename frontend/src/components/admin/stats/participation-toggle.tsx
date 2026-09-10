"use client";

import type { ParticipationModel } from "@/lib/participation-model";
import { PARTICIPATION_HELP, PARTICIPATION_LABELS } from "@/lib/participation-model";

const OPTIONS: ParticipationModel[] = ["historico", "mixto"];

/**
 * Segmented switch between the two participation models. Kept deliberately
 * plain and always visible: mid-draft you need to see which model the board in
 * front of you is using without opening anything.
 */
export function ParticipationToggle({
  value,
  onChange,
  disabled = false,
}: {
  value: ParticipationModel;
  onChange: (model: ParticipationModel) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-vpv-text-muted">Participación</span>
      <div className="flex overflow-hidden rounded border border-vpv-border">
        {OPTIONS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            disabled={disabled}
            aria-pressed={value === option}
            title={PARTICIPATION_HELP[option]}
            className={`px-2 py-1 text-[10px] font-medium transition disabled:opacity-50 ${
              value === option
                ? "bg-vpv-accent text-white"
                : "text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {PARTICIPATION_LABELS[option]}
          </button>
        ))}
      </div>
    </div>
  );
}
