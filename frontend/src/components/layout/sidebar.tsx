"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { NavIcon } from "@/components/ui/nav-icon";
import { Logo } from "@/components/ui/logo";
import { SeasonSelector } from "./season-selector";
import { PERM, userHasPerm } from "@/lib/permissions";

interface DeadlineCheck {
  has_lineup: boolean;
  minutes_remaining: number | null;
  matchday_number: number;
}

type IconName = "home" | "trophy" | "calendar" | "users" | "shuffle" | "coins" | "shield" | "clipboard" | "medal";

type NavItem = {
  href: string;
  label: string;
  icon: IconName;
  appliesTo?: "all" | "league" | "tournament";
};

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Inicio", icon: "home" },
  { href: "/clasificacion", label: "Clasificacion", icon: "trophy" },
  { href: "/acierto", label: "Acierto", icon: "clipboard" },
  // Liga-only
  { href: "/palmares", label: "Palmares", icon: "medal", appliesTo: "league" },
  { href: "/copa", label: "Copa", icon: "shield", appliesTo: "league" },
  // Tournament-only (paginas creadas en Fase 6)
  { href: "/grupos", label: "Grupos", icon: "trophy", appliesTo: "tournament" },
  { href: "/bracket", label: "Cuadro de eliminatorias", icon: "shuffle", appliesTo: "tournament" },
  { href: "/playoffs", label: "Playoffs", icon: "medal", appliesTo: "tournament" },
  { href: "/predicciones", label: "Predicciones", icon: "clipboard", appliesTo: "tournament" },
  // Common
  { href: "/jornadas", label: "Jornadas", icon: "calendar" },
  { href: "/economia", label: "Economia", icon: "coins" },
  { href: "/drafts", label: "Drafts", icon: "shuffle" },
];

/** Permission required for each admin route. null = admin-only. */
const ROUTE_PERM: Record<string, number | null> = {
  "/admin/temporadas": null,
  "/admin/jornadas": PERM.MATCHDAYS,
  "/admin/jugadores": PERM.PLAYERS,
  "/admin/estadisticas": PERM.STATS,
  "/admin/usuarios": null,
  "/admin/invitaciones": null,
  "/admin/economia": PERM.ECONOMY,
  "/admin/participantes": PERM.PARTICIPANTS,
  "/admin/alineaciones": PERM.LINEUPS_ADMIN,
  "/admin/scraping": PERM.SCRAPING,
  "/admin/logros": PERM.ACHIEVEMENTS,
  "/admin/predicciones": PERM.STATS,
  "/admin/grupos": PERM.PLAYERS,
  "/admin/telegram": PERM.TELEGRAM,
  "/admin/backup": null,
};

/**
 * Items that operate on a specific season. Rendered once per active
 * competition (Liga + Tournament). Clicking switches the season context.
 */
const PER_SEASON_ADMIN_ITEMS: { href: string; label: string; appliesTo?: "league" | "tournament" }[] = [
  { href: "/admin/jornadas", label: "Jornadas" },
  { href: "/admin/alineaciones", label: "Alineaciones" },
  { href: "/admin/jugadores", label: "Jugadores" },
  { href: "/admin/estadisticas", label: "Estadisticas" },
  { href: "/admin/economia", label: "Economia" },
  { href: "/admin/participantes", label: "Participantes" },
  { href: "/admin/grupos", label: "Grupos", appliesTo: "tournament" },
  { href: "/admin/logros", label: "Logros", appliesTo: "league" },
  { href: "/admin/predicciones", label: "Predicciones" },
];

/** Items global (no scoped por temporada). */
const GLOBAL_ADMIN_SECTIONS = [
  {
    group: "Sistema",
    items: [
      { href: "/admin/temporadas", label: "Temporadas" },
      { href: "/admin/usuarios", label: "Usuarios" },
      { href: "/admin/invitaciones", label: "Invitaciones" },
    ],
  },
  {
    group: "Operaciones",
    items: [
      { href: "/admin/scraping", label: "Scraping" },
      { href: "/admin/telegram", label: "Telegram" },
      { href: "/admin/backup", label: "Backup" },
    ],
  },
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
  const { selectedSeason, isTournamentContext } = useSeason();
  const prevPathname = useRef(pathname);

  // Hide Pagometro/Economia surfaces for seasons without the weekly
  // payments mechanic. `undefined` keeps the historic behavior so
  // older bundles don't lose the entry.
  const economyEnabled = selectedSeason?.weekly_payments_enabled !== false;

  const visibleNavItems = NAV_ITEMS.filter((item) => {
    if (item.href === "/economia" && !economyEnabled) return false;
    if (!item.appliesTo || item.appliesTo === "all") return true;
    if (item.appliesTo === "league") return !isTournamentContext;
    if (item.appliesTo === "tournament") return isTournamentContext;
    return true;
  });

  // Determine which matchday to link "Introducir equipo" to
  const { data: deadlineCheck } = useFetch<DeadlineCheck>(
    user && selectedSeason
      ? `/lineups/${selectedSeason.id}/deadline-status`
      : null,
  );
  const lineupMatchday = (() => {
    const current = selectedSeason?.matchday_current ?? 0;
    const maxMatchday = selectedSeason?.matchday_end ?? 38;
    if (current === 0) return 1;
    if (!deadlineCheck) return current;
    // If deadline hasn't passed, link to current matchday
    if (deadlineCheck.minutes_remaining !== null && deadlineCheck.minutes_remaining > 0) {
      return current;
    }
    // Deadline passed — link to next matchday (capped at matchday_end)
    return Math.min(current + 1, maxMatchday);
  })();

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
            className="text-vpv-accent"
            onClick={onClose}
          >
            <Logo className="h-12 w-auto" />
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
            {visibleNavItems.map(({ href, label, icon }) => {
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

          {user && (
            <>
              <div className="my-3 border-t border-vpv-border" />
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
                Mi zona
              </p>
              <ul className="space-y-1">
                {selectedSeason && (
                  <li>
                    <Link
                      href={`/jornadas/${lineupMatchday}/alineacion`}
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
                )}
                <li>
                  <Link
                    href="/perfil"
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      pathname === "/perfil"
                        ? "bg-vpv-accent/10 text-vpv-accent"
                        : "text-vpv-text-muted hover:bg-vpv-bg hover:text-vpv-text"
                    }`}
                  >
                    <NavIcon name="users" className="h-5 w-5" />
                    Mi perfil
                  </Link>
                </li>
              </ul>
            </>
          )}

          {user && (user.isAdmin || user.permissions > 0) && (
            <>
              <div className="my-3 border-t border-vpv-border" />
              <ul className="space-y-1">
                {user && userHasPerm(user.isAdmin, user.permissions, PERM.DRAFT) && (
                  <li>
                    <Link
                      href="/drafts/gestionar"
                      className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                        pathname.startsWith("/drafts/gestionar")
                          ? "bg-vpv-accent/10 text-vpv-accent"
                          : "text-vpv-text-muted hover:bg-vpv-bg hover:text-vpv-text"
                      }`}
                    >
                      <NavIcon name="clipboard" className="h-5 w-5" />
                      Gestionar Draft
                    </Link>
                  </li>
                )}
                <AdminSubmenu pathname={pathname} isAdmin={user.isAdmin} permissions={user.permissions} />
              </ul>
            </>
          )}
        </nav>
      </aside>
    </>
  );
}

/**
 * Filter per-season items by user permissions and the season's kind.
 */
function filterSeasonItems(
  items: typeof PER_SEASON_ADMIN_ITEMS,
  kind: "league" | "tournament",
  isAdmin: boolean,
  permissions: number,
) {
  return items.filter((item) => {
    // Filter by kind
    if (item.appliesTo && item.appliesTo !== kind) return false;
    if (isAdmin) return true;
    const perm = ROUTE_PERM[item.href];
    if (perm === null) return false;
    return userHasPerm(isAdmin, permissions, perm);
  });
}

function AdminSubmenu({
  pathname,
  isAdmin,
  permissions,
}: {
  pathname: string;
  isAdmin: boolean;
  permissions: number;
}) {
  const { activeLeague, activeTournament, selectSeason } = useSeason();
  const isInAdmin = pathname.startsWith("/admin");
  const [expanded, setExpanded] = useState(isInAdmin);

  // Build sections: one per active competition + global. Drop the
  // per-season admin "Economia" entry when the season has no weekly
  // payments mechanic — the page would only show empty data.
  const dropEconomyIfDisabled = (
    items: typeof PER_SEASON_ADMIN_ITEMS,
    season: typeof activeLeague,
  ) =>
    season?.weekly_payments_enabled === false
      ? items.filter((item) => item.href !== "/admin/economia")
      : items;

  const ligaItems = activeLeague
    ? dropEconomyIfDisabled(
        filterSeasonItems(PER_SEASON_ADMIN_ITEMS, "league", isAdmin, permissions),
        activeLeague,
      )
    : [];
  const tournamentItems = activeTournament
    ? dropEconomyIfDisabled(
        filterSeasonItems(PER_SEASON_ADMIN_ITEMS, "tournament", isAdmin, permissions),
        activeTournament,
      )
    : [];

  const globalSections = isAdmin
    ? GLOBAL_ADMIN_SECTIONS
    : GLOBAL_ADMIN_SECTIONS.map((section) => ({
        ...section,
        items: section.items.filter((item) => {
          const perm = ROUTE_PERM[item.href];
          if (perm === null) return false;
          return userHasPerm(isAdmin, permissions, perm);
        }),
      })).filter((section) => section.items.length > 0);

  const hasAnyItems =
    ligaItems.length > 0 ||
    tournamentItems.length > 0 ||
    globalSections.length > 0;

  if (!hasAnyItems) return null;

  return (
    <li>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
          isInAdmin
            ? "bg-vpv-accent/10 text-vpv-accent"
            : "text-vpv-text-muted hover:bg-vpv-bg hover:text-vpv-text"
        }`}
      >
        <NavIcon name="shield" className="h-5 w-5" />
        <span className="flex-1 text-left">Admin</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`h-4 w-4 transition-transform ${expanded ? "rotate-180" : ""}`}
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      {expanded && (
        <div className="ml-4 mt-1 space-y-3 border-l border-vpv-border pl-3">
          {activeLeague && ligaItems.length > 0 && (
            <CompetitionAdminSection
              icon="⚽"
              title={activeLeague.name}
              seasonId={activeLeague.id}
              items={ligaItems}
              pathname={pathname}
              onSelectSeason={selectSeason}
            />
          )}
          {activeTournament && tournamentItems.length > 0 && (
            <CompetitionAdminSection
              icon="🏆"
              title={activeTournament.name}
              seasonId={activeTournament.id}
              items={tournamentItems}
              pathname={pathname}
              onSelectSeason={selectSeason}
            />
          )}
          {globalSections.map((section) => (
            <div key={section.group}>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-vpv-text-muted/50">
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
                        className={`block rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                          active
                            ? "text-vpv-accent"
                            : "text-vpv-text-muted hover:text-vpv-text"
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
      )}
    </li>
  );
}

function CompetitionAdminSection({
  icon,
  title,
  seasonId,
  items,
  pathname,
  onSelectSeason,
}: {
  icon: string;
  title: string;
  seasonId: number;
  items: { href: string; label: string }[];
  pathname: string;
  onSelectSeason: (id: number) => void;
}) {
  return (
    <div>
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-vpv-text-muted/50">
        {icon} {title}
      </p>
      <ul className="space-y-0.5">
        {items.map(({ href, label }) => {
          const active =
            pathname === href || pathname.startsWith(href + "/");
          return (
            <li key={href}>
              <Link
                href={href}
                onClick={() => onSelectSeason(seasonId)}
                className={`block rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? "text-vpv-accent"
                    : "text-vpv-text-muted hover:text-vpv-text"
                }`}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
