"use client";
import type { ReactElement } from "react";
import { AnswerCard } from "./answer-card";
import type { PanelProps } from "./contracts";
import { Composer, ContextControls, ProviderControls } from "./controls";
import { usePanel } from "./use-panel";

type State = ReturnType<typeof usePanel>;

function Actions({ state }: {state: State}): ReactElement {
  const disabled = state.query.loading || !state.saved.ready || !state.provider.options?.enabled;
  return <div className="flex flex-wrap gap-3 text-xs">
    <select aria-label="Detalle V2" value={state.mode} onChange={(e) => state.setMode(e.target.value === "quick" ? "quick" : "detailed")}>
      <option value="quick">Rápido</option><option value="detailed">Análisis detallado</option></select>
    <button disabled={disabled} onClick={() => state.send("Evalúa mi próximo pick con los filtros y jugadores seleccionados.")}>Evaluar pick</button>
    <button disabled={disabled} onClick={() => state.send("Explica y compara los jugadores seleccionados; indica qué datos faltan.")}>Explicar / comparar</button>
    <button disabled={disabled} onClick={() => { if (window.confirm("¿Borrar únicamente la conversación V2 de este draft?")) void state.saved.clear(); }}>Borrar historial V2</button>
    {state.query.lastQuestion && <button disabled={disabled} onClick={() => state.send(state.query.lastQuestion)}>Reintentar última pregunta</button>}
  </div>;
}

function Conversation({ state, onSelect }: {state: State; onSelect: (id: number) => void}): ReactElement {
  return <div className="max-h-[32rem] space-y-3 overflow-y-auto" aria-live="polite">
    {state.saved.history.exchanges.map((exchange, i) => <section key={i} className="space-y-2">
      <p className="rounded bg-vpv-accent/10 p-2 text-sm">{exchange.question}</p>
      <AnswerCard answer={exchange.answer} revision={state.revision} onSelect={onSelect}
        refresh={() => state.send(exchange.question)} />
    </section>)}
    {state.query.loading && <p role="status">{state.query.progress}…</p>}
    {[state.provider.error, state.saved.error, state.query.error].filter(Boolean)
      .map((error) => <p key={error} role="alert" className="text-sm text-red-400">{error}</p>)}
  </div>;
}

export function ExperimentalPanel(props: PanelProps): ReactElement {
  const state = usePanel(props);
  return <div className="space-y-3 rounded-lg border border-vpv-card-border bg-vpv-card p-4 text-vpv-text">
    <h3 className="font-semibold">Asistente experimental V2</h3>
    <p className="text-xs text-vpv-text-muted">Solo lectura. Historial privado por usuario y draft.
      Cada envío consulta únicamente el proveedor elegido. Para comparar, copia una pregunta al chat Actual y envíala allí manualmente.</p>
    <ProviderControls options={state.provider.options} provider={state.provider.provider} model={state.provider.model}
      disabled={state.query.loading} change={(p, m) => { state.provider.setProvider(p); state.provider.setModel(m); }} />
    <ContextControls props={props} target={state.target} setTarget={state.setTarget} selected={state.selected} setSelected={state.setSelected} />
    <Actions state={state} />
    <Conversation state={state} onSelect={props.onSelect} />
    <Composer input={state.input} setInput={state.setInput} loading={state.query.loading}
      disabled={!state.saved.ready || !state.provider.options?.enabled || !state.provider.model}
      submit={() => state.send(state.input)} cancel={state.query.cancel} />
    <p className="text-[11px] text-vpv-text-muted">Preguntas, historial y datos consultados se envían al proveedor seleccionado.
      Las etiquetas de participantes no incluyen nombres, pero el texto que escribas puede contenerlos.</p>
  </div>;
}
