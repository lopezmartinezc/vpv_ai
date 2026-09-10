import type { ReactElement } from "react";
import type { Capabilities, PanelProps } from "./contracts";

export function ProviderControls({ options, provider, model, disabled, change }: {
  options: Capabilities | null; provider: string; model: string; disabled: boolean;
  change: (provider: "openai" | "anthropic", model: string) => void;
}): ReactElement {
  const current = options?.providers.find((p) => p.name === provider);
  return <div className="flex gap-2 text-xs"><select aria-label="Proveedor V2" value={provider} disabled={disabled}
    onChange={(e) => { const p = options?.providers.find((p) => p.name === e.target.value);
      if (p) change(p.name, p.default_model); }}>
    {options?.providers.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}</select>
    <select aria-label="Modelo V2" value={model} disabled={disabled} onChange={(e) => {
      if (current) change(current.name, e.target.value); }}>
      {current?.models.map((m) => <option key={m} value={m}>{m}</option>)}</select></div>;
}

export function ContextControls({ props, target, setTarget, selected, setSelected }: {
  props: PanelProps; target: number | null; setTarget: (id: number | null) => void;
  selected: number[]; setSelected: (ids: number[]) => void;
}): ReactElement {
  return <div className="grid gap-2 text-xs sm:grid-cols-2">
    <label>Plantilla consultada<select className="block w-full" value={target ?? ""}
      onChange={(e) => setTarget(e.target.value ? Number(e.target.value) : null)}>
      <option value="">Mi plantilla (usuario autenticado)</option>
      {props.participants.map((p) => <option key={p.participant_id} value={p.participant_id}>{p.display_name}</option>)}
    </select></label>
    <label>Comparar (hasta 3 jugadores)<select multiple className="block w-full" value={selected.map(String)}
      onChange={(e) => setSelected(Array.from(e.target.selectedOptions).slice(0, 3).map((o) => Number(o.value)))}>
      {props.players.map((p) => <option key={p.player_id} value={p.player_id}>{p.display_name}</option>)}
    </select></label>
    <p>Jugador abierto: {props.players.find((p) => p.player_id === props.context.selected_player_ids[0])?.display_name ?? "ninguno"}.
      Filtros: {props.context.position || "todas las posiciones"} · {props.context.team || "todos los equipos"}
      {" · "}{props.context.order}.</p>
  </div>;
}

export function Composer({ input, setInput, loading, disabled, submit, cancel }: {
  input: string; setInput: (text: string) => void; loading: boolean; disabled: boolean;
  submit: () => void; cancel: () => void;
}): ReactElement {
  return <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
    <input aria-label="Pregunta V2" className="min-w-0 flex-1 rounded border p-2" value={input} maxLength={4000}
      onChange={(e) => setInput(e.target.value)} placeholder="Pregunta sobre el draft…" />
    {loading ? <button type="button" onClick={cancel}>Cancelar</button>
      : <button type="submit" disabled={disabled || !input.trim()}>Enviar V2</button>}
  </form>;
}
