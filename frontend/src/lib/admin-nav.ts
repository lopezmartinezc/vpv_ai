import { PERM, userHasPerm } from "@/lib/permissions";

/**
 * Single source of truth for the admin navigation.
 *
 * Both the global sidebar (`components/layout/sidebar.tsx`) and the admin
 * section rail (`app/admin/layout.tsx`) render from this list, so they can
 * never drift apart again. Grouping mirrors the backend permission model:
 *
 * - "season"     — per-season tasks, delegable by a Perm bit; shown under the
 *                  active competition (Liga / Torneo).
 * - "operations" — cross-season tools, delegable by a Perm bit.
 * - "system"     — super-admin only (`is_admin`, no bit): season/user/backup admin.
 */
export type AdminScope = "season" | "operations" | "system";

export type AdminNavItem = {
  href: string;
  label: string;
  /** Perm bit required, or null for super-admin-only (is_admin). */
  perm: number | null;
  scope: AdminScope;
  /** Season items only: restrict to a competition kind. Absent = both. */
  appliesTo?: "league" | "tournament";
};

export const ADMIN_ITEMS: AdminNavItem[] = [
  // TEMPORADA — per-season, shown under each active competition.
  { href: "/admin/jornadas", label: "Jornadas", perm: PERM.MATCHDAYS, scope: "season" },
  { href: "/admin/alineaciones", label: "Alineaciones", perm: PERM.LINEUPS_ADMIN, scope: "season" },
  { href: "/admin/jugadores", label: "Jugadores", perm: PERM.PLAYERS, scope: "season" },
  { href: "/admin/estadisticas", label: "Estadísticas", perm: PERM.STATS, scope: "season" },
  { href: "/admin/predicciones", label: "Predicciones", perm: PERM.STATS, scope: "season" },
  { href: "/admin/economia", label: "Economía", perm: PERM.ECONOMY, scope: "season" },
  { href: "/admin/participantes", label: "Participantes", perm: PERM.PARTICIPANTS, scope: "season" },
  { href: "/admin/grupos", label: "Grupos", perm: PERM.PLAYERS, scope: "season", appliesTo: "tournament" },
  { href: "/admin/logros", label: "Logros", perm: PERM.ACHIEVEMENTS, scope: "season", appliesTo: "league" },
  { href: "/admin/marca", label: "Notas Periódicos", perm: PERM.MARCA, scope: "season" },
  { href: "/drafts/gestionar", label: "Draft", perm: PERM.DRAFT, scope: "season" },
  { href: "/plantillas", label: "Plantillas", perm: null, scope: "season" },

  // OPERACIONES — cross-season tools.
  { href: "/admin/scraping", label: "Scraping", perm: PERM.SCRAPING, scope: "operations" },
  { href: "/admin/telegram", label: "Telegram", perm: PERM.TELEGRAM, scope: "operations" },

  // SISTEMA — super-admin only.
  { href: "/admin/temporadas", label: "Temporadas", perm: null, scope: "system" },
  { href: "/admin/usuarios", label: "Usuarios", perm: null, scope: "system" },
  { href: "/admin/invitaciones", label: "Invitaciones", perm: null, scope: "system" },
  { href: "/admin/backup", label: "Backup", perm: null, scope: "system" },
];

/** Route → required perm (null = admin-only). Derived, replaces the old duplicated maps. */
export const ROUTE_PERM: Record<string, number | null> = Object.fromEntries(
  ADMIN_ITEMS.map((i) => [i.href, i.perm]),
);

/** Whether a user may see an admin item. Admin sees all; null perm is admin-only. */
export function canSeeAdminItem(
  isAdmin: boolean,
  permissions: number,
  item: AdminNavItem,
): boolean {
  if (isAdmin) return true;
  if (item.perm === null) return false;
  return userHasPerm(isAdmin, permissions, item.perm);
}

/** Season-scoped items for a competition kind (respects appliesTo). */
export function seasonItems(kind: "league" | "tournament"): AdminNavItem[] {
  return ADMIN_ITEMS.filter(
    (i) => i.scope === "season" && (!i.appliesTo || i.appliesTo === kind),
  );
}

export const operationsItems: AdminNavItem[] = ADMIN_ITEMS.filter(
  (i) => i.scope === "operations",
);
export const systemItems: AdminNavItem[] = ADMIN_ITEMS.filter((i) => i.scope === "system");

/** Label of the admin item matching a pathname (for the mobile header). */
export function adminLabelForPath(pathname: string): string {
  const hit = ADMIN_ITEMS.find(
    (i) => pathname === i.href || pathname.startsWith(i.href + "/"),
  );
  return hit?.label ?? "Admin";
}
