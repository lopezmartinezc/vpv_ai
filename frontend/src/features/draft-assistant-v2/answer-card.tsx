import type { ReactElement } from "react";
import type { Answer, Card, Revision } from "./contracts";

function Metric({ label, value }: { label: string; value: string | number | null }): ReactElement {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-wide text-vpv-text-muted">{label}</p>
      <p className="text-xs font-medium tabular-nums text-vpv-text">{value ?? "—"}</p>
    </div>
  );
}

function PlayerCard({
  card,
  onSelect,
}: {
  card: Card;
  onSelect: (id: number) => void;
}): ReactElement {
  return (
    <div className="rounded-md border border-vpv-card-border bg-vpv-card p-2.5">
      <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
        <button
          type="button"
          className="text-sm font-semibold text-vpv-accent hover:underline"
          onClick={() => onSelect(card.player_id)}
        >
          {card.name}
        </button>
        <span className="text-[10px] text-vpv-text-muted">
          {card.position} · {card.team}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-[9px] font-medium ${
            card.available
              ? "bg-green-500/10 text-green-400"
              : "bg-red-500/10 text-red-400"
          }`}
        >
          {card.available ? "Disponible" : "No disponible"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Metric label="Prioridad" value={card.priority} />
        <Metric label="Base" value={card.priority_base} />
        <Metric label="VORP" value={card.vorp} />
        <Metric label="Salto" value={card.available_gap} />
        <Metric label="Mejora XI" value={card.marginal_gain} />
      </div>

      <p className="mt-1.5 text-[9px] text-vpv-text-muted">
        Mejora XI = sobre tu once actual; no cuenta la cobertura futura.
      </p>

      {card.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {card.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-vpv-card-border px-2 py-0.5 text-[9px] text-vpv-text-muted"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function AnswerCard({
  answer,
  revision,
  onSelect,
  refresh,
}: {
  answer: Answer;
  revision: Revision | null;
  onSelect: (id: number) => void;
  refresh: () => void;
}): ReactElement {
  const stale =
    answer.status === "stale" ||
    (revision !== null &&
      (revision.draft !== answer.revision.draft || revision.board !== answer.revision.board));

  return (
    <article className="space-y-2 rounded-lg border border-vpv-card-border bg-vpv-bg p-3">
      <p className="flex flex-wrap items-center gap-x-1.5 text-[10px] text-vpv-text-muted">
        <span className="rounded bg-vpv-card px-1.5 py-0.5 font-medium text-vpv-text">
          {answer.provider}
        </span>
        <span>{answer.model}</span>
        <span>·</span>
        <span>tras pick #{answer.revision.pick_count}</span>
        <span>·</span>
        <span className="tabular-nums">{new Date(answer.revision.at).toLocaleTimeString()}</span>
      </p>

      {(stale || !revision || answer.status === "incomplete") && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 text-xs text-amber-400"
        >
          <span>
            {stale
              ? "Datos desactualizados: no uses esta recomendación sin actualizar."
              : answer.status === "incomplete"
                ? "Análisis incompleto."
                : "Vigencia pendiente de comprobar."}
          </span>
          <button
            type="button"
            className="rounded border border-amber-500/50 px-2 py-0.5 font-medium hover:bg-amber-500/20"
            onClick={refresh}
          >
            Actualizar análisis
          </button>
        </p>
      )}

      <p className="whitespace-pre-wrap text-sm leading-relaxed text-vpv-text">{answer.text}</p>

      {answer.warnings.map((w) => (
        <p key={w} className="text-[11px] text-amber-500">
          {w}
        </p>
      ))}

      {!stale && answer.cards.length > 0 && (
        <div className="space-y-2">
          {answer.cards.map((card) => (
            <PlayerCard key={card.player_id} card={card} onSelect={onSelect} />
          ))}
        </div>
      )}

      <details className="text-[10px] text-vpv-text-muted">
        <summary className="cursor-pointer hover:text-vpv-text">Evidencia y consumo</summary>
        <p className="mt-1 break-all">{answer.evidence_ids.join(" · ")}</p>
        <p className="mt-1 tabular-nums">
          {answer.usage.latency_ms} ms · {answer.usage.tool_calls} herramientas ·{" "}
          {answer.usage.input_tokens} tokens entrada · {answer.usage.output_tokens} salida
        </p>
      </details>
    </article>
  );
}
