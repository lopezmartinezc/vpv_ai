"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";

const ADMIN_NAV = [
  {
    group: "Liga",
    items: [
      { href: "/admin/temporadas", label: "Temporadas" },
      { href: "/admin/jornadas", label: "Jornadas" },
      { href: "/admin/jugadores", label: "Jugadores" },
      { href: "/admin/estadisticas", label: "Estadisticas" },
    ],
  },
  {
    group: "Usuarios",
    items: [
      { href: "/admin/usuarios", label: "Usuarios" },
      { href: "/admin/invitaciones", label: "Invitaciones" },
      { href: "/admin/economia", label: "Economia" },
    ],
  },
  {
    group: "Operaciones",
    items: [
      { href: "/admin/scraping", label: "Scraping" },
      { href: "/admin/telegram", label: "Telegram" },
      { href: "/admin/backup", label: "Backup" },
      { href: "/admin/logros", label: "Logros" },
    ],
  },
  {
    group: "Gestion",
    items: [
      { href: "/plantillas", label: "Plantillas" },
      { href: "/drafts/gestionar", label: "Drafts" },
    ],
  },
];

function getActiveLabel(pathname: string): string {
  for (const section of ADMIN_NAV) {
    for (const item of section.items) {
      if (pathname === item.href || pathname.startsWith(item.href + "/")) {
        return item.label;
      }
    }
  }
  return "Admin";
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  if (!user?.isAdmin) {
    router.push("/");
    return null;
  }

  const navContent = (
    <div className="space-y-5">
      {ADMIN_NAV.map((section) => (
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
          {getActiveLabel(pathname)}
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
