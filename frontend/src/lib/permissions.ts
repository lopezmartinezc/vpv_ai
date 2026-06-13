/** Bitmap permissions — must match backend src/shared/permissions.py */
export const PERM = {
  SCRAPING: 1,
  STATS: 2,
  ACHIEVEMENTS: 4,
  DRAFT: 8,
  ECONOMY: 16,
  TELEGRAM: 32,
  MATCHDAYS: 64,
  PLAYERS: 128,
  LINEUPS_ADMIN: 256,
  PARTICIPANTS: 512,
  MARCA: 1024,
} as const;

export type PermKey = keyof typeof PERM;

/** Labels for UI display */
export const PERM_LABELS: Record<PermKey, string> = {
  SCRAPING: "Scraping",
  STATS: "Estadisticas",
  ACHIEVEMENTS: "Logros",
  DRAFT: "Draft",
  ECONOMY: "Economia",
  TELEGRAM: "Telegram",
  MATCHDAYS: "Jornadas",
  PLAYERS: "Jugadores",
  LINEUPS_ADMIN: "Alineaciones admin",
  PARTICIPANTS: "Participantes",
  MARCA: "Notas Marca",
};

/** Check if a permissions bitmap includes a specific permission */
export function hasPerm(permissions: number, perm: number): boolean {
  return (permissions & perm) !== 0;
}

/** Check if user (admin or permissions bitmap) has a specific permission */
export function userHasPerm(
  isAdmin: boolean,
  permissions: number,
  perm: number
): boolean {
  return isAdmin || hasPerm(permissions, perm);
}
