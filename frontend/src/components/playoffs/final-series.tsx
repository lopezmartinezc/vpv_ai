import type { CompetitionSummary, FinalLeg, FinalSeries } from "@/types";

// A season can have more than one playoff (the Liga has Apertura and
// Clausura), and the Liga final is played over three jornadas.

export const PLAYOFF_STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente",
  regular: "Fase regular",
  ko: "Eliminatorias",
  completed: "Finalizado",
};

/** The playoff to open first: the one being played, else the last one
 *  finished, else the first. */
export function defaultPlayoff(playoffs: CompetitionSummary[]): CompetitionSummary | null {
  const live = playoffs.find((p) => p.status === "regular" || p.status === "ko");
  if (live) return live;
  const done = playoffs.filter((p) => p.status === "completed");
  return done[done.length - 1] ?? playoffs[0] ?? null;
}

function nameOf(series: FinalSeries, side: "a" | "b"): string {
  return (side === "a" ? series.participant_a_name : series.participant_b_name) ?? "Por decidir";
}

/** What happened in one jornada of the final, in words. */
export function legOutcome(series: FinalSeries, leg: FinalLeg): string {
  if (leg.result === "not_needed") return "No se disputa";
  if (leg.result !== "a" && leg.result !== "b") {
    return leg.score_a !== null && leg.score_a === leg.score_b
      ? "Empate: se decide con las otras jornadas"
      : "Pendiente";
  }
  const winner = nameOf(series, leg.result);
  if (leg.decided_by === "difference") return `Empate: para ${winner} por diferencia`;
  if (leg.decided_by === "seed") return `Empate: para ${winner} por clasificación`;
  return `Gana ${winner}`;
}

/** "Jornada 2 de 3 · vas 1-0", or who won once it is settled. */
export function seriesLine(
  series: FinalSeries | null | undefined,
  matchupId: number,
  participantId: number | null,
): string | null {
  if (!series) return null;
  const index = series.legs.findIndex((leg) => leg.matchup_id === matchupId);
  if (index < 0) return null;
  if (series.winner_participant_id !== null) {
    return series.winner_participant_id === participantId
      ? "Final decidida: ¡eres campeón!"
      : `Final decidida: campeón ${series.winner_name ?? ""}`.trim();
  }
  const isA = participantId === series.participant_a_id;
  const own = isA ? series.wins_a : series.wins_b;
  const rival = isA ? series.wins_b : series.wins_a;
  return `Jornada ${index + 1} de ${series.legs.length} · vas ${own}-${rival}`;
}

/** The final as a series: jornadas won, each jornada, and the champion. */
export function FinalSeriesView({ series }: { series: FinalSeries }) {
  const winner = series.winner_participant_id;
  const strong = (id: number | null) =>
    winner !== null && winner === id ? "font-bold text-vpv-text" : "text-vpv-text";

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-card-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
        Final · al mejor de {series.legs.length}
      </div>
      <div className="flex items-center justify-between px-3 py-2 text-sm">
        <span className={`flex-1 truncate ${strong(series.participant_a_id)}`}>
          {nameOf(series, "a")}
        </span>
        <span
          className="mx-3 tabular-nums font-bold text-vpv-accent"
          aria-label={`Jornadas ganadas ${series.wins_a} a ${series.wins_b}`}
        >
          {series.wins_a} — {series.wins_b}
        </span>
        <span className={`flex-1 truncate text-right ${strong(series.participant_b_id)}`}>
          {nameOf(series, "b")}
        </span>
      </div>
      <ul className="divide-y divide-vpv-border/40 border-t border-vpv-card-border">
        {series.legs.map((leg, i) => (
          <li
            key={leg.matchup_id}
            className={`flex items-center justify-between gap-2 px-3 py-1.5 text-xs ${
              leg.result === "not_needed" ? "text-vpv-text-muted/60" : "text-vpv-text-muted"
            }`}
          >
            <span>
              Jornada {i + 1}
              {leg.matchday_number !== null && ` · J${leg.matchday_number}`}
            </span>
            <span className="tabular-nums text-vpv-text">
              {leg.result === "not_needed" ? "—" : `${leg.score_a ?? "—"} — ${leg.score_b ?? "—"}`}
            </span>
            <span className="flex-1 truncate text-right">{legOutcome(series, leg)}</span>
          </li>
        ))}
      </ul>
      {series.winner_name && (
        <p className="border-t border-vpv-card-border px-3 py-2 text-xs font-semibold text-vpv-success">
          Campeón: {series.winner_name}
        </p>
      )}
    </div>
  );
}
