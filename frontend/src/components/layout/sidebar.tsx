"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { NavIcon } from "@/components/ui/nav-icon";
import { SeasonSelector } from "./season-selector";

const NAV_ITEMS = [
  { href: "/", label: "Inicio", icon: "home" },
  { href: "/clasificacion", label: "Liga", icon: "trophy" },
  { href: "/copa", label: "Copa", icon: "shield" },
  { href: "/jornadas", label: "Jornadas", icon: "calendar" },
  { href: "/plantillas", label: "Plantillas", icon: "users" },
  { href: "/drafts", label: "Drafts", icon: "shuffle" },
  { href: "/economia", label: "Economia", icon: "coins" },
] as const;

export function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const { user } = useAuth();
  const { selectedSeason } = useSeason();
  const prevPathname = useRef(pathname);

  // Close on route change
  useEffect(() => {
    if (prevPathname.current !== pathname) {
      prevPathname.current = pathname;
      onClose();
    }
  }, [pathname, onClose]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      {/* Overlay */}
      <div
        className={`fixed inset-0 z-40 bg-black/50 transition-opacity duration-300 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-vpv-card shadow-xl transition-transform duration-300 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-vpv-border px-4 py-4">
          <Link
            href="/"
            className="text-lg font-bold text-vpv-accent"
            onClick={onClose}
          >
            Liga VPV
          </Link>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-vpv-text-muted transition-colors hover:text-vpv-text"
            aria-label="Cerrar menu"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
            >
              <line x1={18} y1={6} x2={6} y2={18} />
              <line x1={6} y1={6} x2={18} y2={18} />
            </svg>
          </button>
        </div>

        {/* User + Season */}
        <div className="border-b border-vpv-border px-4 py-3">
          {user && (
            <p className="mb-2 text-sm font-medium text-vpv-text">
              {user.username}
            </p>
          )}
          <SeasonSelector />
        </div>

        {/* Nav items */}
        <nav className="flex-1 overflow-y-auto px-3 py-3">
          <ul className="space-y-1">
            {NAV_ITEMS.map(({ href, label, icon }) => {
              const active =
                href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      active
                        ? "bg-vpv-accent/10 text-vpv-accent"
                        : "text-vpv-text-muted hover:bg-vpv-bg hover:text-vpv-text"
                    }`}
                  >
                    <NavIcon name={icon} className="h-5 w-5" />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>

          {user && selectedSeason && (
            <>
              <div className="my-3 border-t border-vpv-border" />
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
                Mi zona
              </p>
              <ul className="space-y-1">
                <li>
                  <Link
                    href={`/jornadas/${selectedSeason.matchday_current + 1}/alineacion`}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      pathname.includes("/alineacion")
                        ? "bg-vpv-accent/10 text-vpv-accent"
                        : "text-vpv-text-muted hover:bg-vpv-bg hover:text-vpv-text"
                    }`}
                  >
                    <NavIcon name="clipboard" className="h-5 w-5" />
                    Introducir equipo
                  </Link>
                </li>
              </ul>
            </>
          )}

          {user?.isAdmin && (
            <>
              <div className="my-3 border-t border-vpv-border" />
              <ul>
                <li>
                  <Link
                    href="/admin"
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      pathname.startsWith("/admin")
                        ? "bg-vpv-accent/10 text-vpv-accent"
                        : "text-vpv-text-muted hover:bg-vpv-bg hover:text-vpv-text"
                    }`}
                  >
                    <NavIcon name="shield" className="h-5 w-5" />
                    Admin
                  </Link>
                </li>
              </ul>
            </>
          )}
        </nav>
      </aside>
    </>
  );
}
