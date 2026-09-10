import type { ReactElement } from "react";
import { confidenceDots, confidenceFor } from "@/lib/draft-confidence";
import type { Card } from "./contracts";

type Numeric = (c: Card) => number | null | undefined;

interface MetricRow {
  label: string;
  value: Numeric;
  /** How to print it; the ranking uses the raw number. */
  format: (v: number) => string;
  /** Lower is better for nothing here today, but the row says so explicitly. */
  higherIsBetter: boolean;
  hint?: string;
}

const pct = (v: number): string => `${(v * 100).toFixed(0)}%`;
const one = (v: number): string => v.toFixed(1);
const whole = (v: number): string => v.toFixed(0);

const ROWS: MetricRow[] = [
  { label: "Prioridad", value: (c) => c.priority, format: whole, higherIsBetter: true, hint: "Proyección del resto de temporada, ajustada por riesgo y tags." },
  { label: "Base", value: (c) => c.priority_base, format: whole, higherIsBetter: true, hint: "La misma proyección sin tus tags." },
  { label: "VORP", value: (c) => c.vorp, format: one, higherIsBetter: true, hint: "Valor sobre el reemplazo de su posición." },
  { label: "Mejora XI", value: (c) => c.marginal_gain, format: whole, higherIsBetter: true, hint: "Puntos alineables que gana tu once actual con él." },
  { label: "Participación", value: (c) => c.participation, format: pct, higherIsBetter: true, hint: "Fracción de jornadas restantes en las que se espera que juegue." },
  { label: "Jornadas est.", value: (c) => c.exp_games_remaining, format: one, higherIsBetter: true },
  { label: "Media pts", value: (c) => c.avg_points, format: one, higherIsBetter: true, hint: "Puntos por partido jugado." },
  { label: "PJ", value: (c) => c.games_played, format: whole, higherIsBetter: true },
  { label: "Titular", value: (c) => c.availability, format: pct, higherIsBetter: true, hint: "Partidos con 45+ minutos." },
  { label: "Salto", value: (c) => c.available_gap, format: whole, higherIsBetter: true, hint: "Distancia al siguiente disponible de su posición." },
];

function best(values: (number | null | undefined)[], higherIsBetter: boolean): number | null {
  const present = values.filter((v): v is number => typeof v === "number");
  if (present.length < 2) return null;
  return higherIsBetter ? Math.max(...present) : Math.min(...present);
}

function confidence(c: Card) {
  return confidenceFor({
    seasons_played: c.seasons_played ?? 0,
    availability: c.availability ?? null,
    is_new: c.is_new,
    team_changed: c.team_changed,
    position_changed: c.position_changed,
  });
}

/**
 * Two or three players, side by side, best value in each row marked.
 *
 * Stacked cards make you read the same label six times and hold the numbers
 * in your head; a table makes the winner of each row visible at a glance,
 * which is the whole point of asking for a comparison.
 */
export function ComparisonTable({ cards, onSelect }: { cards: Card[]; onSelect: (id: number) => void }): ReactElement {
  const confidences = cards.map(confidence);
  const bestConfidence = best(confidences.map((c) => c.score), true);

  return (
    <div className="overflow-x-auto rounded-md border border-vpv-card-border">
      <table className="w-full min-w-[28rem] text-xs">
        <thead>
          <tr className="border-b border-vpv-card-border bg-vpv-card">
            <th scope="col" className="w-28 px-2 py-2 text-left text-[9px] font-medium uppercase tracking-wide text-vpv-text-muted">
              Métrica
            </th>
            {cards.map((c) => (
              <th key={c.player_id} scope="col" className="px-2 py-2 text-left align-top">
                <button
                  type="button"
                  onClick={() => onSelect(c.player_id)}
                  className="text-sm font-semibold text-vpv-accent hover:underline"
                >
                  {c.name}
                </button>
                <div className="mt-0.5 flex flex-wrap items-center gap-1 text-[10px] font-normal text-vpv-text-muted">
                  <span>{c.position} · {c.team}</span>
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                      c.available ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
                    }`}
                  >
                    {c.available ? "Disponible" : "No disponible"}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => {
            const values = cards.map(row.value);
            const top = best(values, row.higherIsBetter);
            return (
              <tr key={row.label} className="border-b border-vpv-card-border/60 last:border-0">
                <th scope="row" title={row.hint} className="px-2 py-1.5 text-left font-medium text-vpv-text-muted">
                  {row.label}
                </th>
                {cards.map((c, i) => {
                  const v = values[i];
                  const isBest = typeof v === "number" && top !== null && v === top;
                  return (
                    <td
                      key={c.player_id}
                      className={`px-2 py-1.5 tabular-nums ${isBest ? "font-semibold text-green-400" : "text-vpv-text"}`}
                    >
                      {typeof v === "number" ? row.format(v) : "—"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
          <tr className="border-b border-vpv-card-border/60">
            <th scope="row" className="px-2 py-1.5 text-left font-medium text-vpv-text-muted" title="Cuánta evidencia hay detrás de la proyección.">
              Confianza
            </th>
            {cards.map((c, i) => {
              const conf = confidences[i];
              const isBest = bestConfidence !== null && conf.score === bestConfidence;
              return (
                <td
                  key={c.player_id}
                  title={`Confianza ${conf.level}: ${conf.reason}`}
                  className={`px-2 py-1.5 tracking-tight ${
                    conf.level === "alta" ? "text-green-400" : conf.level === "media" ? "text-amber-400" : "text-red-400"
                  } ${isBest ? "font-semibold" : ""}`}
                >
                  {confidenceDots(conf.level)}
                  <span className="ml-1 text-[9px] text-vpv-text-muted">{conf.reason}</span>
                </td>
              );
            })}
          </tr>
          <tr>
            <th scope="row" className="px-2 py-1.5 text-left font-medium text-vpv-text-muted">Tags</th>
            {cards.map((c) => (
              <td key={c.player_id} className="px-2 py-1.5">
                {c.tags.length === 0 ? (
                  <span className="text-vpv-text-muted">—</span>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {c.tags.map((t) => (
                      <span key={t} className="rounded-full border border-vpv-card-border px-1.5 py-0.5 text-[9px] text-vpv-text-muted">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
