"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import {
  type AdminNavItem,
  adminLabelForPath,
  canSeeAdminItem,
  operationsItems,
  seasonItems,
  systemItems,
} from "@/lib/admin-nav";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const { activeLeague, activeTournament } = useSeason();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Same 3-tier structure as the global sidebar, from the shared admin-nav:
  // per-competition "Temporada" sections + "Operaciones" + "Sistema".
  const filteredNav = useMemo(() => {
    if (!user) return [];
    const { isAdmin, permissions } = user;
    const visible = (items: AdminNavItem[]) =>
      items.filter((item) => canSeeAdminItem(isAdmin, permissions, item));
    const dropEconomy = (items: AdminNavItem[], season: typeof activeLeague) =>
      season?.weekly_payments_enabled === false
        ? items.filter((i) => i.href !== "/admin/economia")
        : items;

    const sections: { group: string; items: AdminNavItem[] }[] = [];
    if (activeLeague) {
      sections.push({
        group: `⚽ ${activeLeague.name}`,
        items: dropEconomy(visible(seasonItems("league")), activeLeague),
      });
    }
    if (activeTournament) {
      sections.push({
        group: `🏆 ${activeTournament.name}`,
        items: dropEconomy(visible(seasonItems("tournament")), activeTournament),
      });
    }
    sections.push({ group: "Operaciones", items: visible(operationsItems) });
    sections.push({ group: "Sistema", items: visible(systemItems) });
    return sections.filter((s) => s.items.length > 0);
  }, [user, activeLeague, activeTournament]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  if (!user || (!user.isAdmin && user.permissions === 0)) {
    router.push("/");
    return null;
  }

  const navContent = (
    <div className="space-y-5">
      {filteredNav.map((section) => (
        <div key={section.group}>
          <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-widest text-vpv-text-muted/60">
            {section.group}
          </p>
          <ul className="space-y-0.5">
            {section.items.map(({ href, label }) => {
              const active =
                pathname === href || pathname.startsWith(href + "/");
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={() => setMobileOpen(false)}
                    className={`block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      active
                        ? "bg-vpv-accent/15 text-vpv-accent"
                        : "text-vpv-text-muted hover:bg-vpv-bg hover:text-vpv-text"
                    }`}
                  >
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );

  return (
    <div>
      {/* Mobile header */}
      <div className="mb-4 flex items-center justify-between lg:hidden">
        <h1 className="text-xl font-bold text-vpv-text">Admin</h1>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="flex items-center gap-2 rounded-lg border border-vpv-border bg-vpv-card px-3 py-2 text-sm font-medium text-vpv-text transition-colors hover:bg-vpv-bg"
        >
          {adminLabelForPath(pathname)}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`h-4 w-4 transition-transform ${mobileOpen ? "rotate-180" : ""}`}
          >
            <path
              fillRule="evenodd"
              d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>

      {/* Mobile dropdown */}
      {mobileOpen && (
        <div className="mb-4 rounded-lg border border-vpv-card-border bg-vpv-card p-3 lg:hidden">
          {navContent}
        </div>
      )}

      {/* Desktop: sidebar + content */}
      <div className="lg:flex lg:gap-6">
        {/* Desktop sidebar */}
        <aside className="hidden w-48 flex-shrink-0 lg:block">
          <h1 className="mb-4 text-xl font-bold text-vpv-text">Admin</h1>
          {navContent}
        </aside>

        {/* Content */}
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
