"use client";

import Image from "next/image";
import { useState } from "react";

// The Liga's playoffs carry David Silva's name, in his memory. Tournaments keep
// the plain "Playoffs".
export const LIGA_PLAYOFF_LABEL = "Playoff DS";
export const LIGA_PLAYOFF_TITLE = "PLAYOFF DAVID SILVA";
export const LIGA_PLAYOFF_BADGE = "/playoffs/playoff-ds.webp";

/** Banner at the top of the Liga's playoff page: his badge and the name. */
export function PlayoffDsHero({ subtitle }: { subtitle?: string }) {
  // The badge is copied to the server by hand: without it, the name stands alone.
  const [badge, setBadge] = useState(true);

  return (
    <div className="flex items-center gap-4 rounded-2xl border border-orange-500/40 bg-[#0d0d0d] px-5 py-5 sm:gap-6 sm:px-7">
      {badge && (
        <div className="relative h-20 w-20 shrink-0 sm:h-28 sm:w-28">
          <Image
            src={LIGA_PLAYOFF_BADGE}
            alt="Escudo del Playoff David Silva"
            fill
            sizes="(min-width: 640px) 112px, 80px"
            className="rounded-full object-contain"
            priority
            onError={() => setBadge(false)}
          />
        </div>
      )}
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold uppercase leading-tight tracking-wide text-orange-500 sm:text-4xl">
          {LIGA_PLAYOFF_TITLE}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-orange-200/80">{subtitle}</p>}
      </div>
    </div>
  );
}
