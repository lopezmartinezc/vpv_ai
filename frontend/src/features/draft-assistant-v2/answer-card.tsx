import type { ReactElement } from "react";
import type { Answer, Card, Revision } from "./contracts";

function PlayerCard({ card, onSelect }: {card: Card; onSelect: (id: number) => void}): ReactElement {
  return <div className="rounded border border-vpv-card-border p-2 text-xs">
    <button type="button" className="font-semibold text-vpv-accent underline" onClick={() => onSelect(card.player_id)}>
      {card.name}</button> · {card.position} · {card.team}
    <p>{card.available ? "Disponible en la consulta" : "No disponible"}</p>
    <p>Prioridad {card.priority ?? "—"} · Base {card.priority_base ?? "—"} · VORP {card.vorp ?? "—"}</p>
    <p>Salto entre disponibles {card.available_gap ?? "—"}</p>
    <p>Mejora del XI actual {card.marginal_gain ?? "—"} (no incluye cobertura futura)</p>
    <p>{card.tags.join(" · ")}</p>
  </div>;
}

export function AnswerCard({ answer, revision, onSelect, refresh }: {
  answer: Answer; revision: Revision | null; onSelect: (id: number) => void; refresh: () => void;
}): ReactElement {
  const stale = answer.status === "stale" || (revision !== null &&
    (revision.draft !== answer.revision.draft || revision.board !== answer.revision.board));
  return <article className="space-y-2 rounded bg-vpv-bg p-3 text-sm">
    <p className="text-xs text-vpv-text-muted">{answer.provider} · {answer.model} · Tras pick #{answer.revision.pick_count}
      {" · "}{new Date(answer.revision.at).toLocaleTimeString()}</p>
    {(stale || !revision || answer.status === "incomplete") && <p role="status" className="text-amber-500">
      {stale ? "Datos desactualizados: no uses esta recomendación sin actualizar."
        : answer.status === "incomplete" ? "Análisis incompleto." : "Vigencia pendiente de comprobar."}
      <button type="button" className="ml-2 underline" onClick={refresh}>Actualizar análisis</button></p>}
    <p className="whitespace-pre-wrap">{answer.text}</p>
    {answer.warnings.map((w) => <p key={w} className="text-xs text-amber-500">{w}</p>)}
    {!stale && answer.cards.map((card) => <PlayerCard key={card.player_id} card={card} onSelect={onSelect} />)}
    <details className="text-xs text-vpv-text-muted"><summary>Evidencia y consumo</summary>
      <p>{answer.evidence_ids.join(" · ")}</p>
      <p>{answer.usage.latency_ms} ms · {answer.usage.tool_calls} herramientas · {answer.usage.input_tokens} tokens entrada
        {" · "}{answer.usage.output_tokens} salida</p></details>
  </article>;
}
