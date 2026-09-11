/**
 * Query for the per-player re-sync, and the warning that goes with it.
 *
 * The matchday range is what separates the two cases the re-pin has to serve.
 * A player wrongly registered at the parent club needs every row moved. A
 * player who genuinely transferred mid-season needs only the rows FROM the
 * transfer onward: the ones before it record the club he was actually at, and
 * rewriting those would replace a truth with a convenience.
 */

export interface ResyncOptions {
  seasonId: number;
  repin: boolean;
  /** First matchday to touch. Empty or invalid means the whole season. */
  fromMatchday?: string;
}

export function resyncQuery({ seasonId, repin, fromMatchday }: ResyncOptions): string {
  const params = new URLSearchParams({
    season_id: String(seasonId),
    repin: String(repin),
  });
  const start = Number(fromMatchday);
  if (fromMatchday?.trim() && Number.isInteger(start) && start >= 1) {
    params.set("start", String(start));
  }
  return params.toString();
}

/** What the admin is about to do, in the words of the two cases. */
export function resyncWarning(playerName: string, fromMatchday?: string): string {
  const start = fromMatchday?.trim();
  const scope = start
    ? `de la jornada ${start} en adelante`
    : "de TODAS las jornadas de la temporada";
  return (
    `¿Reasignar al equipo actual de ${playerName} las jornadas ${scope}?\n\n` +
    (start
      ? "Las jornadas anteriores se quedan como están, que es lo correcto si cambió de equipo a mitad de temporada."
      : "Si cambió de equipo a mitad de temporada, indica primero desde qué jornada: " +
        "sin acotar, las jornadas que jugó en su equipo anterior pasarían a decir el actual.")
  );
}
