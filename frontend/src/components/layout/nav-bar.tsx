"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SeasonSelector } from "./season-selector";

const NAV_ITEMS = [
  { href: "/clasificacion", label: "Clasificacion" },
  { href: "/jornadas", label: "Jornadas" },
  { href: "/plantillas", label: "Plantillas" },
  { href: "/drafts", label: "Drafts" },
  { href: "/economia", label: "Economia" },
] as const;

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-vpv-border bg-vpv-card/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Link href="/" className="text-lg font-bold text-vpv-accent">
          VPV
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                pathname.startsWith(href)
                  ? "bg-vpv-accent/10 text-vpv-accent"
                  : "text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto">
          <SeasonSelector />
        </div>
      </div>
    </header>
  );
}
