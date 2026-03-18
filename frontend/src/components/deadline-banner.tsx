"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { apiClient } from "@/lib/api-client";
import Link from "next/link";

interface DeadlineStatus {
  has_lineup: boolean;
  deadline_at: string | null;
  minutes_remaining: number | null;
  matchday_number: number;
}

function formatRemaining(minutes: number): string {
  if (minutes >= 60) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m > 0 ? `${h}h ${m}min` : `${h}h`;
  }
  return `${minutes}min`;
}

export function DeadlineBanner() {
  const { user } = useAuth();
  const { selectedSeason } = useSeason();
  const [status, setStatus] = useState<DeadlineStatus | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!user || !selectedSeason) return;

    let cancelled = false;

    async function poll() {
      try {
        const data = await apiClient.get<DeadlineStatus>(
          `/lineups/${selectedSeason!.id}/deadline-status`,
        );
        if (!cancelled) setStatus(data);
      } catch {
        if (!cancelled) setStatus(null);
      }
    }

    // Initial fetch + interval
    poll();
    intervalRef.current = setInterval(poll, 60_000);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [user, selectedSeason]);

  if (!status) return null;
  if (status.has_lineup) return null;
  if (status.minutes_remaining === null || status.minutes_remaining <= 0) return null;
  if (status.minutes_remaining > 120) return null;

  const urgent = status.minutes_remaining <= 30;

  return (
    <div
      className={`sticky top-0 z-50 border-b px-4 py-2 text-center text-sm font-medium ${
        urgent
          ? "border-red-700 bg-red-600 text-white"
          : "border-orange-600 bg-orange-500 text-white"
      }`}
    >
      No has enviado alineacion para J{status.matchday_number} — Faltan{" "}
      {formatRemaining(status.minutes_remaining)}
      <Link
        href={`/jornadas/${status.matchday_number}/alineacion`}
        className="ml-3 inline-block rounded bg-white/20 px-2 py-0.5 text-xs font-bold transition-colors hover:bg-white/30"
      >
        Enviar ahora
      </Link>
    </div>
  );
}
