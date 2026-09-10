"use client";
import type { ReactElement } from "react";
import { AnswerCard } from "./answer-card";
import type { PanelProps } from "./contracts";
import { Composer, ContextControls, ProviderControls } from "./controls";
import { usePanel } from "./use-panel";

type State = ReturnType<typeof usePanel>;

const PILL =
  "rounded-full border border-vpv-card-border px-3 py-1 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-40 disabled:hover:text-vpv-text-muted";

/** Openers worth a click. An empty chat that only says "ask me something"
 *  teaches nothing about what this thing can actually answer. */
const OPENERS = [
  { label: "Evaluar pick", prompt: "Evalúa mi próximo pick con los filtros y jugadores seleccionados." },
  { label: "Explicar / comparar", prompt: "Explica y compara los jugadores seleccionados; indica qué datos faltan." },
];

function Actions({ state }: { state: State }): ReactElement {
  const disabled = state.query.loading || !state.saved.ready || !state.provider.options?.enabled;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        aria-label="Detalle V2"
        value={state.mode}
        onChange={(e) => state.setMode(e.target.value === "quick" ? "quick" : "detailed")}
        className="rounded-md border border-vpv-card-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
      >
        <option value="quick">Rápido</option>
        <option value="detailed">Análisis detallado</option>
      </select>
      {OPENERS.map((opener) => (
        <button
          key={opener.label}
          disabled={disabled}
          className={PILL}
          onClick={() => state.send(opener.prompt)}
        >
          {opener.label}
        </button>
      ))}
      {state.query.lastQuestion && (
        <button disabled={disabled} className={PILL} onClick={() => state.send(state.query.lastQuestion)}>
          Reintentar última pregunta
        </button>
      )}
      <button
        disabled={disabled}
        className="ml-auto rounded-full border border-red-500/30 px-3 py-1 text-xs text-red-400 transition-colors hover:bg-red-500/10 disabled:opacity-40"
        onClick={() => {
          if (window.confirm("¿Borrar únicamente la conversación V2 de este draft?")) {
            void state.saved.clear();
          }
        }}
      >
        Borrar historial V2
      </button>
    </div>
  );
}

function Conversation({
  state,
  onSelect,
}: {
  state: State;
  onSelect: (id: number) => void;
}): ReactElement {
  const errors = [state.provider.error, state.saved.error, state.query.error].filter(Boolean);
  const empty = state.saved.history.exchanges.length === 0 && !state.query.loading;

  return (
    <div className="max-h-[32rem] space-y-3 overflow-y-auto" aria-live="polite">
      {empty && (
        <p className="rounded-lg border border-dashed border-vpv-card-border px-3 py-6 text-center text-xs text-vpv-text-muted">
          Sin conversación todavía. Prueba con <span className="text-vpv-text">Evaluar pick</span>,
          o pregunta por un jugador concreto.
        </p>
      )}

      {state.saved.history.exchanges.map((exchange, i) => (
        <section key={i} className="space-y-2">
          <p className="rounded-lg border-l-2 border-vpv-accent bg-vpv-accent/10 px-3 py-2 text-sm text-vpv-text">
            {exchange.question}
          </p>
          <AnswerCard
            answer={exchange.answer}
            revision={state.revision}
            onSelect={onSelect}
            refresh={() => state.send(exchange.question)}
          />
        </section>
      ))}

      {state.query.loading && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-lg border border-vpv-card-border bg-vpv-bg px-3 py-2 text-xs text-vpv-text-muted"
        >
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-vpv-accent" aria-hidden="true" />
          {state.query.progress}…
        </p>
      )}

      {errors.map((error) => (
        <p
          key={error}
          role="alert"
          className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-400"
        >
          {error}
        </p>
      ))}
    </div>
  );
}

export function ExperimentalPanel(props: PanelProps): ReactElement {
  const state = usePanel(props);
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card text-vpv-text">
      <header className="border-b border-vpv-card-border px-4 py-3">
        <h3 className="text-sm font-semibold">Asistente experimental V2</h3>
        <p className="mt-1 text-[11px] leading-relaxed text-vpv-text-muted">
          Solo lectura, con historial privado por usuario y draft. Cada envío consulta únicamente
          el proveedor elegido; para comparar, copia la pregunta al chat Actual y lánzala allí.
        </p>
      </header>

      <div className="space-y-3 px-4 py-3">
        <ProviderControls
          options={state.provider.options}
          provider={state.provider.provider}
          model={state.provider.model}
          disabled={state.query.loading}
          change={(p, m) => {
            state.provider.setProvider(p);
            state.provider.setModel(m);
          }}
        />
        <ContextControls
          props={props}
          target={state.target}
          setTarget={state.setTarget}
          selected={state.selected}
          setSelected={state.setSelected}
        />
        <Actions state={state} />
      </div>

      <div className="border-t border-vpv-card-border px-4 py-3">
        <Conversation state={state} onSelect={props.onSelect} />
      </div>

      <div className="border-t border-vpv-card-border px-4 py-3">
        <Composer
          input={state.input}
          setInput={state.setInput}
          loading={state.query.loading}
          disabled={!state.saved.ready || !state.provider.options?.enabled || !state.provider.model}
          submit={() => state.send(state.input)}
          cancel={state.query.cancel}
        />
        <p className="mt-2 text-[10px] leading-relaxed text-vpv-text-muted">
          Preguntas, historial y datos consultados se envían al proveedor seleccionado. Las
          etiquetas de participantes no incluyen nombres, pero el texto que escribas puede
          contenerlos.
        </p>
      </div>
    </div>
  );
}
