"use client";

import { useEffect, useState, type JSX } from "react";

export type DeadlineTone = "open" | "urgent" | "closed";

/** Last stretch before the deadline, shown in red. */
export const URGENT_MINUTES = 30;

export interface DeadlineState {
  label: string;
  tone: DeadlineTone;
}

/** Reads the API deadline only; null when the server gave no date. */
export function deadlineState(deadlineAt: string | null, now: number): DeadlineState | null {
  const deadline = deadlineAt ? Date.parse(deadlineAt) : NaN;
  if (!Number.isFinite(deadline)) return null;
  if (deadline <= now) return { label: "Plazo cerrado", tone: "closed" };
  const minutes = Math.ceil((deadline - now) / 60_000);
  const hours = Math.floor(minutes / 60);
  const label =
    hours > 0
      ? `Cierre en ${hours}h ${minutes % 60}m`
      : `Cierre en ${minutes} minuto${minutes === 1 ? "" : "s"}`;
  return { label, tone: minutes <= URGENT_MINUTES ? "urgent" : "open" };
}

const TONE_CLASS: Record<DeadlineTone, string> = {
  open: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  urgent: "border-vpv-danger/40 bg-vpv-danger/10 text-vpv-danger",
  closed: "border-vpv-border bg-vpv-card text-vpv-text-muted",
};

const TONE_ICON: Record<DeadlineTone, string> = {
  open: "⏱",
  urgent: "!",
  closed: "\u{1F512}",
};

/** Displays the authoritative API deadline; never reconstructs domain rules. */
export function DeadlineBanner({ deadlineAt }: { deadlineAt: string | null }): JSX.Element | null {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const update = (): void => setNow(Date.now());
    update();
    const timer = setInterval(update, 15_000);
    return () => clearInterval(timer);
  }, []);
  if (now === null) return null;
  const state = deadlineState(deadlineAt, now);
  if (state === null) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium ${TONE_CLASS[state.tone]}`}
    >
      <span aria-hidden="true">{TONE_ICON[state.tone]}</span>
      <span>{state.label}</span>
    </div>
  );
}
