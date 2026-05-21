"use client";

import { resolveCountryCode } from "@/lib/country-flags";

interface CountryFlagProps {
  teamName?: string | null;
  slug?: string | null;
  fallbackLogo?: string | null;
  size?: number;
  className?: string;
  alt?: string;
}

/**
 * Render a national flag for a tournament team. Resolves the team name/slug
 * to an ISO code and serves the SVG from /flags/{iso}.svg. If no mapping is
 * found, falls back to the provided club logo (or nothing).
 *
 * Uses a plain <img> tag to avoid Next.js' SVG-blocking heuristics in
 * next/image; flags are self-hosted SVGs from flag-icons (CC0).
 */
export function CountryFlag({
  teamName,
  slug,
  fallbackLogo,
  size = 20,
  className,
  alt,
}: CountryFlagProps) {
  const iso = resolveCountryCode(teamName, slug);

  if (iso) {
    const width = size;
    const height = Math.round((size * 3) / 4);
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={`/flags/${iso}.svg`}
        alt={alt ?? teamName ?? iso}
        width={width}
        height={height}
        className={`inline-block shrink-0 rounded-sm border border-vpv-border/40 object-cover ${className ?? ""}`}
      />
    );
  }

  if (fallbackLogo) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={fallbackLogo}
        alt={alt ?? teamName ?? "team"}
        width={size}
        height={size}
        className={`inline-block shrink-0 rounded-full ${className ?? ""}`}
      />
    );
  }

  return null;
}
