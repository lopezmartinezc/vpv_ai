"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { NavIcon } from "@/components/ui/nav-icon";

const NAV_ITEMS = [
  { href: "/clasificacion", label: "Clasificacion", icon: "trophy" },
  { href: "/jornadas", label: "Jornadas", icon: "calendar" },
  { href: "/plantillas", label: "Plantillas", icon: "users" },
  { href: "/drafts", label: "Drafts", icon: "shuffle" },
  { href: "/economia", label: "Economia", icon: "coins" },
] as const;

export function NavBar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-vpv-border bg-vpv-card/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Link href="/" className="text-lg font-bold text-vpv-accent">
          VPV
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map(({ href, label, icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-vpv-accent/10 text-vpv-accent"
                    : "text-vpv-text-muted hover:text-vpv-text"
                }`}
              >
                <NavIcon name={icon} className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
          {user?.isAdmin && (
            <Link
              href="/admin"
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                pathname.startsWith("/admin")
                  ? "bg-vpv-accent/10 text-vpv-accent"
                  : "text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              <NavIcon name="shield" className="h-4 w-4" />
              Admin
            </Link>
          )}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <ThemeToggle />
          {user ? (
            <div className="flex items-center gap-2">
              <span className="hidden text-sm text-vpv-text-muted sm:inline">
                {user.username}
              </span>
              <button
                onClick={logout}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-vpv-text-muted transition-colors hover:text-vpv-text"
              >
                Salir
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="rounded-md bg-vpv-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-vpv-accent-hover"
            >
              Entrar
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
