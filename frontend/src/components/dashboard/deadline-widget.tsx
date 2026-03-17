"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

function minutesUntil(isoDate: string): number {
  return Math.max(0, Math.floor((new Date(isoDate).getTime() - Date.now()) / 60_000));
}

export function DeadlineWidget({
  firstMatchAt,
  deadlineMin,
  matchdayNumber,
}: {
  firstMatchAt: string | null;
  deadlineMin: number;
  matchdayNumber: number;
}) {
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (!firstMatchAt) return;
    const deadlineMs = new Date(firstMatchAt).getTime() - deadlineMin * 60_000;
    const deadlineIso = new Date(deadlineMs).toISOString();
    const update = () => setRemaining(minutesUntil(deadlineIso));
    update();
    const id = setInterval(update, 30_000);
    return () => clearInterval(id);
  }, [firstMatchAt, deadlineMin]);

  if (remaining === null || remaining <= 0) return null;

  const isUrgent = remaining <= 60;
  const days = Math.floor(remaining / 1440);
  const hours = Math.floor((remaining % 1440) / 60);
  const mins = remaining % 60;

  let label: string;
  if (days > 0) {
    label = `${days}d ${hours}h`;
  } else if (hours > 0) {
    label = `${hours}h ${mins}m`;
  } else {
    label = `${mins} minuto${mins !== 1 ? "s" : ""}`;
  }

  return (
    <Link
      href={`/jornadas/${matchdayNumber}/alineacion`}
      className={`flex items-center justify-between gap-3 rounded-lg border px-4 py-3 transition-colors hover:brightness-110 ${
        isUrgent
          ? "border-red-500/40 bg-red-500/10"
          : "border-amber-500/30 bg-amber-500/10"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-lg" aria-hidden="true">
          {isUrgent ? "!" : "\u23F1"}
        </span>
        <div>
          <p
            className={`text-sm font-semibold ${isUrgent ? "text-red-400" : "text-amber-400"}`}
          >
            Deadline J{matchdayNumber}
          </p>
          <p className="text-xs text-vpv-text-muted">
            Envia tu alineacion antes de que cierre
          </p>
        </div>
      </div>
      <span
        className={`rounded-lg px-3 py-1.5 text-sm font-bold tabular-nums ${
          isUrgent
            ? "bg-red-500/20 text-red-400"
            : "bg-amber-500/20 text-amber-400"
        }`}
      >
        {label}
      </span>
    </Link>
  );
}
