"use client";

import Image from "next/image";
import { useSeason } from "@/contexts/season-context";

/**
 * Big themed banner shown at the top of tournament pages.
 * For Mundial 2026 uses the official emblem + rotating host mascots
 * (Maple, Zayu, Clutch).
 *
 * Static assets live in public/tournaments/{type}/.
 */
export function TournamentHero({
  title,
  subtitle,
  mascot,
}: {
  title: string;
  subtitle?: string;
  /** Force a specific mascot. Default rotates per page. */
  mascot?: "maple" | "zayu" | "clutch" | "auto";
}) {
  const { selectedSeason } = useSeason();
  const tournamentType = selectedSeason?.tournament_type ?? "mundial";
  const resolvedMascot = mascot ?? pickMascot(title);

  return (
    <div className="tournament-hero relative overflow-hidden rounded-2xl px-6 py-8 shadow-lg sm:px-8 sm:py-10">
      {/* Decorative pattern */}
      <DecorativePattern type={tournamentType} />

      <div className="relative z-10 flex items-center gap-4 sm:gap-6">
        {/* Logo emblem */}
        {tournamentType === "mundial" ? (
          <div className="relative h-20 w-20 shrink-0 sm:h-28 sm:w-28">
            <Image
              src="/tournaments/mundial/logo.webp"
              alt="FIFA World Cup 2026"
              fill
              sizes="(min-width: 640px) 112px, 80px"
              className="object-contain drop-shadow-lg"
              priority
            />
          </div>
        ) : (
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-white/15 text-5xl backdrop-blur-sm sm:h-24 sm:w-24">
            ⭐
          </div>
        )}

        {/* Title block */}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/80">
            {selectedSeason?.name ?? "Torneo"}
          </p>
          <h1 className="mt-1 text-3xl font-bold leading-tight text-white sm:text-4xl">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-2 text-sm text-white/90 sm:text-base">{subtitle}</p>
          )}
        </div>

        {/* Mascot (desktop only, hidden on small screens) */}
        {tournamentType === "mundial" && resolvedMascot !== "auto" && (
          <div className="relative hidden h-32 w-32 shrink-0 md:block">
            <Image
              src={`/tournaments/mundial/mascot-${resolvedMascot}.avif`}
              alt={`Mascota ${resolvedMascot}`}
              fill
              sizes="128px"
              className="object-contain drop-shadow-xl"
            />
          </div>
        )}
      </div>
    </div>
  );
}

/** Pick a stable mascot per page title so each section looks different. */
function pickMascot(title: string): "maple" | "zayu" | "clutch" {
  const mascots: Array<"maple" | "zayu" | "clutch"> = ["maple", "zayu", "clutch"];
  const hash = title.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return mascots[hash % mascots.length];
}

function DecorativePattern({ type }: { type: string }) {
  if (type === "mundial") {
    return (
      <svg
        className="pointer-events-none absolute -right-12 -top-12 h-72 w-72 opacity-15"
        viewBox="0 0 200 200"
        fill="none"
      >
        {/* Globe meridians */}
        <circle cx="100" cy="100" r="85" stroke="white" strokeWidth="1.5" />
        <ellipse cx="100" cy="100" rx="85" ry="40" stroke="white" strokeWidth="1.5" />
        <ellipse cx="100" cy="100" rx="85" ry="20" stroke="white" strokeWidth="1.5" />
        <line x1="15" y1="100" x2="185" y2="100" stroke="white" strokeWidth="1.5" />
        <line x1="100" y1="15" x2="100" y2="185" stroke="white" strokeWidth="1.5" />
        <ellipse cx="100" cy="100" rx="40" ry="85" stroke="white" strokeWidth="1.5" />
      </svg>
    );
  }
  return (
    <svg
      className="pointer-events-none absolute -right-12 -top-12 h-72 w-72 opacity-15"
      viewBox="0 0 200 200"
      fill="none"
    >
      {Array.from({ length: 12 }).map((_, i) => {
        const angle = (i * 30 * Math.PI) / 180;
        const x = 100 + Math.cos(angle) * 70;
        const y = 100 + Math.sin(angle) * 70;
        return (
          <text
            key={i}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="20"
            fill="white"
          >
            ★
          </text>
        );
      })}
    </svg>
  );
}
