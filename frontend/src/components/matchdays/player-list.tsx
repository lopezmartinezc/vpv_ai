import type { LineupPlayerEntry } from "@/types";

const POSITION_COLORS: Record<string, string> = {
  POR: "bg-amber-500/20 text-amber-400",
  DEF: "bg-blue-500/20 text-blue-400",
  MED: "bg-green-500/20 text-green-400",
  DEL: "bg-red-500/20 text-red-400",
};

function PositionBadge({ pos }: { pos: string }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-bold ${POSITION_COLORS[pos] ?? "bg-vpv-border text-vpv-text-muted"}`}
    >
      {pos}
    </span>
  );
}

export function PlayerList({ players }: { players: LineupPlayerEntry[] }) {
  return (
    <>
      {/* Mobile: Cards */}
      <div className="space-y-2 md:hidden">
        {players.map((p) => (
          <div
            key={p.player_id}
            className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3"
          >
            <div className="flex items-center gap-2">
              <PositionBadge pos={p.position_slot} />
              <span className="flex-1 truncate font-medium text-vpv-text">
                {p.player_name}
              </span>
              <span className="text-lg font-bold tabular-nums text-vpv-text">
                {p.points}
              </span>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <span className="text-xs text-vpv-text-muted">
                {p.team_name}
              </span>
              {p.score_breakdown && (
                <span className="text-[10px] tabular-nums text-vpv-text-muted">
                  Jug {p.score_breakdown.pts_play + p.score_breakdown.pts_starter}
                  {" "}&middot; Res {p.score_breakdown.pts_result}
                  {p.score_breakdown.pts_goals !== 0 &&
                    ` \u00b7 Gol ${p.score_breakdown.pts_goals}`}
                  {p.score_breakdown.pts_assists !== 0 &&
                    ` \u00b7 Asi ${p.score_breakdown.pts_assists}`}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden overflow-x-auto rounded-lg border border-vpv-card-border md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="px-3 py-3">Pos</th>
              <th className="px-3 py-3">Jugador</th>
              <th className="px-3 py-3">Equipo</th>
              <th className="px-2 py-3 text-center">Jug</th>
              <th className="px-2 py-3 text-center">Res</th>
              <th className="px-2 py-3 text-center">Gol</th>
              <th className="px-2 py-3 text-center">Asi</th>
              <th className="px-2 py-3 text-center">Imb</th>
              <th className="px-2 py-3 text-center">Tar</th>
              <th className="px-2 py-3 text-center">Val</th>
              <th className="px-3 py-3 text-right">Pts</th>
            </tr>
          </thead>
          <tbody>
            {players.map((p) => {
              const b = p.score_breakdown;
              return (
                <tr
                  key={p.player_id}
                  className="border-b border-vpv-border last:border-0"
                >
                  <td className="px-3 py-2.5">
                    <PositionBadge pos={p.position_slot} />
                  </td>
                  <td className="px-3 py-2.5 font-medium text-vpv-text">
                    {p.player_name}
                  </td>
                  <td className="px-3 py-2.5 text-vpv-text-muted">
                    {p.team_name}
                  </td>
                  <td className="px-2 py-2.5 text-center tabular-nums">
                    {b ? b.pts_play + b.pts_starter : "–"}
                  </td>
                  <td className="px-2 py-2.5 text-center tabular-nums">
                    {b?.pts_result ?? "–"}
                  </td>
                  <td className="px-2 py-2.5 text-center tabular-nums">
                    {b?.pts_goals ?? "–"}
                  </td>
                  <td className="px-2 py-2.5 text-center tabular-nums">
                    {b?.pts_assists ?? "–"}
                  </td>
                  <td className="px-2 py-2.5 text-center tabular-nums">
                    {b?.pts_clean_sheet ?? "–"}
                  </td>
                  <td className="px-2 py-2.5 text-center tabular-nums">
                    {b ? b.pts_yellow + b.pts_red : "–"}
                  </td>
                  <td className="px-2 py-2.5 text-center tabular-nums">
                    {b ? b.pts_marca + b.pts_as : "–"}
                  </td>
                  <td className="px-3 py-2.5 text-right font-bold tabular-nums text-vpv-text">
                    {p.points}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
