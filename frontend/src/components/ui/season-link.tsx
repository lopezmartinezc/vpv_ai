"use client";

import Link from "next/link";
import type { ComponentProps, ReactElement } from "react";
import { useSeason } from "@/contexts/season-context";
import { withSeason } from "@/lib/season-link";

/**
 * `next/link` that carries the season being viewed, when the target belongs to
 * a season. The one place the rule lives: a page opts in by importing this
 * instead of `next/link`, and every link on it keeps the season.
 *
 * Do not use it for a link that already names its own season — the admin
 * menu's Torneo section, say. It would overwrite that season with the one
 * being viewed. Use `hrefForSeason` with a plain `next/link` there.
 */
export function SeasonLink({ href, ...rest }: ComponentProps<typeof Link>): ReactElement {
  const { selectedSeason } = useSeason();
  const target = typeof href === "string" ? withSeason(href, selectedSeason?.id) : href;
  return <Link href={target} {...rest} />;
}
