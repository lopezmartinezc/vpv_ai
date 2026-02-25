import Link from "next/link";
import { NavIcon } from "@/components/ui/nav-icon";

interface NavCardData {
  title: string;
  href: string;
  icon: "trophy" | "calendar" | "users" | "shuffle" | "coins";
  detail: string;
}

export function NavCards({ cards }: { cards: NavCardData[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map(({ title, href, icon, detail }) => (
        <Link
          key={href}
          href={href}
          className="flex items-center gap-3 rounded-lg border border-vpv-card-border bg-vpv-card p-4 transition-colors hover:border-vpv-accent"
        >
          <NavIcon name={icon} className="h-6 w-6 text-vpv-accent" />
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-vpv-text">{title}</h2>
            <p className="truncate text-xs text-vpv-text-muted">{detail}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}
