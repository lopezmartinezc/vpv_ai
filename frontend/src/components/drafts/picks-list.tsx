import type { DraftPickEntry } from "@/types";

const POSITION_COLORS: Record<string, string> = {
  POR: "text-amber-400",
  DEF: "text-blue-400",
  MED: "text-green-400",
  DEL: "text-red-400",
};

export function PicksList({ picks }: { picks: DraftPickEntry[] }) {
  return (
    <>
      {/* Mobile: Cards */}
      <div className="space-y-2 md:hidden">
        {picks.map((pick) => (
          <div
            key={pick.pick_number}
            className="flex items-center gap-3 rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3"
          >
            <span className="w-6 text-center text-xs tabular-nums text-vpv-text-muted">
              {pick.pick_number}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-vpv-text">
                {pick.player_name}
              </p>
              <p className="text-xs text-vpv-text-muted">
                <span className={POSITION_COLORS[pick.position] ?? ""}>
                  {pick.position}
                </span>
                {" "}&middot; {pick.team_name}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-vpv-text">
                {pick.display_name}
              </p>
              <p className="text-[10px] text-vpv-text-muted">
                R{pick.round_number}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden overflow-x-auto rounded-lg border border-vpv-card-border md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-card text-left text-vpv-text-muted">
              <th className="w-14 px-4 py-2 text-center">#</th>
              <th className="w-14 px-4 py-2 text-center">Ronda</th>
              <th className="px-4 py-2">Participante</th>
              <th className="px-4 py-2">Jugador</th>
              <th className="w-14 px-4 py-2 text-center">Pos</th>
              <th className="px-4 py-2">Equipo</th>
            </tr>
          </thead>
          <tbody>
            {picks.map((pick) => (
              <tr
                key={pick.pick_number}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-accent/5"
              >
                <td className="px-4 py-2 text-center tabular-nums text-vpv-text-muted">
                  {pick.pick_number}
                </td>
                <td className="px-4 py-2 text-center tabular-nums text-vpv-text-muted">
                  {pick.round_number}
                </td>
                <td className="px-4 py-2 font-medium text-vpv-text">
                  {pick.display_name}
                </td>
                <td className="px-4 py-2 text-vpv-text">
                  {pick.player_name}
                </td>
                <td
                  className={`px-4 py-2 text-center text-xs font-bold ${POSITION_COLORS[pick.position] ?? ""}`}
                >
                  {pick.position}
                </td>
                <td className="px-4 py-2 text-vpv-text-muted">
                  {pick.team_name}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
