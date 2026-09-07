"use client";

/**
 * TeamCounter — how many players you've drafted from each real La Liga team.
 * Helps avoid over-loading a single club (rotation/collapse risk). Highlights a
 * club once you hold 4+ of its players. Same visibility as RosterCounter (the
 * participant's own squad).
 */
export function TeamCounter({ teams }: { teams: string[] }) {
  if (teams.length === 0) return null;

  const counts: Record<string, number> = {};
  for (const t of teams) counts[t] = (counts[t] ?? 0) + 1;
  const rows = Object.entries(counts).sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
  );

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
      <div className="mb-1.5 flex flex-wrap items-baseline gap-2">
        <h4 className="text-xs font-semibold text-vpv-text">Por equipo</h4>
        <span className="text-[10px] text-vpv-text-muted">
          jugadores que llevas de cada equipo · {teams.length} en total
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {rows.map(([team, n]) => (
          <span
            key={team}
            title={n >= 4 ? "Muchos de un mismo equipo: riesgo si rota o pincha" : undefined}
            className={`flex items-center gap-1 rounded border px-2 py-1 text-xs ${
              n >= 4
                ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
                : "border-vpv-border bg-vpv-bg text-vpv-text"
            }`}
          >
            {team} <b className="tabular-nums">×{n}</b>
          </span>
        ))}
      </div>
    </div>
  );
}
