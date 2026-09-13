/**
 * Links that remember which season you are looking at.
 *
 * The season context reads `?season=` first (#138). But almost every link in
 * the app pointed at a bare path, so the parameter was dropped on the first
 * click: open `/?season=B`, press Clasificación, and you were back on whatever
 * the browser had stored — season A (IN-01 in the web audit). Storage is shared
 * by every tab, so two tabs on two seasons could never both hold.
 *
 * This decides, for any internal path, whether it belongs to a season and so
 * should carry it. A few routes are about no season in particular and are left
 * exactly as they are.
 */

// Routes that are about no season: history across all of them, the user's own
// account, and the tools that act on the whole system.
const GLOBAL_ROUTES = [
  "/palmares",
  "/perfil",
  "/login",
  "/registro",
  "/admin/scraping",
  "/admin/telegram",
  "/admin/temporadas",
  "/admin/usuarios",
  "/admin/invitaciones",
  "/admin/backup",
];

function splitOnce(value: string, separator: string): [string, string] {
  const at = value.indexOf(separator);
  return at === -1 ? [value, ""] : [value.slice(0, at), value.slice(at + 1)];
}

/** Whether an internal path belongs to a season. External links never do. */
export function isSeasonScoped(path: string): boolean {
  if (!path.startsWith("/") || path.startsWith("//")) return false;
  const [pathname] = splitOnce(splitOnce(path, "#")[0], "?");
  return !GLOBAL_ROUTES.some((route) => pathname === route || pathname.startsWith(route + "/"));
}

/**
 * `path` carrying `?season=<id>` when it belongs to a season. Keeps any query
 * and hash already there, and replaces a stale season rather than adding a
 * second one.
 */
export function withSeason(path: string, seasonId: number | null | undefined): string {
  if (seasonId == null || !isSeasonScoped(path)) return path;
  const [beforeHash, hash] = splitOnce(path, "#");
  const [pathname, query] = splitOnce(beforeHash, "?");
  const params = new URLSearchParams(query);
  params.set("season", String(seasonId));
  return `${pathname}?${params.toString()}${hash ? `#${hash}` : ""}`;
}
