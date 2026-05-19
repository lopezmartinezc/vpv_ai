"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSeason } from "@/contexts/season-context";
import { NavIcon } from "@/components/ui/nav-icon";

type IconName =
  | "home"
  | "trophy"
  | "calendar"
  | "users"
  | "shuffle"
  | "coins"
  | "shield"
  | "clipboard"
  | "medal";

type Tab = {
  href: string;
  label: string;
  icon: IconName;
  appliesTo?: "all" | "league" | "tournament";
};

const LEAGUE_TABS: Tab[] = [
  { href: "/clasificacion", label: "Clasif", icon: "trophy" },
  { href: "/copa", label: "Copa", icon: "shield", appliesTo: "league" },
  { href: "/jornadas", label: "Jornadas", icon: "calendar" },
  { href: "/economia", label: "Economia", icon: "coins" },
];

const TOURNAMENT_TABS: Tab[] = [
  { href: "/clasificacion", label: "Clasif", icon: "trophy" },
  { href: "/grupos", label: "Grupos", icon: "shield", appliesTo: "tournament" },
  { href: "/bracket", label: "Bracket", icon: "shuffle", appliesTo: "tournament" },
  { href: "/jornadas", label: "Jornadas", icon: "calendar" },
];

export function BottomNav() {
  const pathname = usePathname();
  const { isTournamentContext } = useSeason();
  const tabs = isTournamentContext ? TOURNAMENT_TABS : LEAGUE_TABS;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-vpv-border bg-vpv-card/95 backdrop-blur md:hidden">
      <div className="flex h-14 items-center justify-around">
        {tabs.map(({ href, label, icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] transition-colors active:scale-95 ${
                active ? "text-vpv-accent" : "text-vpv-text-muted"
              }`}
            >
              <NavIcon name={icon} className="h-5 w-5" />
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
