import type { ReactElement } from "react";
import type { Capabilities, PanelProps } from "./contracts";
import { PlayerPicker } from "./player-picker";

/** House input styling, so V2 reads as the same application as everything else. */
const FIELD =
  "rounded-md border border-vpv-card-border bg-vpv-bg px-2 py-1.5 text-xs text-vpv-text disabled:opacity-50";
const LABEL = "block text-[10px] font-medium uppercase tracking-wide text-vpv-text-muted";

export function ProviderControls({
  options,
  provider,
  model,
  disabled,
  change,
}: {
  options: Capabilities | null;
  provider: string;
  model: string;
  disabled: boolean;
  change: (provider: "openai" | "anthropic", model: string) => void;
}): ReactElement {
  const current = options?.providers.find((p) => p.name === provider);
  return (
    <div className="flex flex-wrap items-end gap-2">
      <div>
        <span className={LABEL}>Proveedor</span>
        <select
          aria-label="Proveedor V2"
          value={provider}
          disabled={disabled}
          className={`${FIELD} mt-1 w-32`}
          onChange={(e) => {
            const next = options?.providers.find((p) => p.name === e.target.value);
            if (next) change(next.name, next.default_model);
          }}
        >
          {options?.providers.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name}
            </option>
          ))}
        </select>
      </div>
      <div className="min-w-0 flex-1">
        <span className={LABEL}>Modelo</span>
        <select
          aria-label="Modelo V2"
          value={model}
          disabled={disabled}
          className={`${FIELD} mt-1 w-full`}
          onChange={(e) => {
            if (current) change(current.name, e.target.value);
          }}
        >
          {current?.models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export function ContextControls({
  props,
  target,
  setTarget,
  selected,
  setSelected,
}: {
  props: PanelProps;
  target: number | null;
  setTarget: (id: number | null) => void;
  selected: number[];
  setSelected: (ids: number[]) => void;
}): ReactElement {
  const open = props.players.find((p) => p.player_id === props.context.selected_player_ids[0]);

  return (
    <div className="space-y-2 rounded-md border border-vpv-card-border bg-vpv-bg/40 p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label>
          <span className={LABEL}>Plantilla consultada</span>
          <select
            className={`${FIELD} mt-1 w-full`}
            value={target ?? ""}
            onChange={(e) => setTarget(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Mi plantilla (usuario autenticado)</option>
            {props.participants.map((p) => (
              <option key={p.participant_id} value={p.participant_id}>
                {p.display_name}
              </option>
            ))}
          </select>
        </label>
        <PlayerPicker players={props.players} selected={selected} onChange={setSelected} />
      </div>


      <p className="text-[10px] text-vpv-text-muted">
        Jugador abierto:{" "}
        <span className="text-vpv-text">{open?.display_name ?? "ninguno"}</span> · Filtros:{" "}
        <span className="text-vpv-text">{props.context.position || "todas las posiciones"}</span> ·{" "}
        <span className="text-vpv-text">{props.context.team || "todos los equipos"}</span> ·{" "}
        <span className="text-vpv-text">{props.context.order}</span>
      </p>
    </div>
  );
}

export function Composer({
  input,
  setInput,
  loading,
  disabled,
  submit,
  cancel,
}: {
  input: string;
  setInput: (text: string) => void;
  loading: boolean;
  disabled: boolean;
  submit: () => void;
  cancel: () => void;
}): ReactElement {
  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <input
        aria-label="Pregunta V2"
        className="min-w-0 flex-1 rounded-md border border-vpv-card-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text placeholder:text-vpv-text-muted"
        value={input}
        maxLength={4000}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Pregunta sobre el draft…"
      />
      {loading ? (
        <button
          type="button"
          onClick={cancel}
          className="rounded-md border border-vpv-card-border px-3 py-2 text-sm font-medium text-vpv-text-muted hover:text-vpv-text"
        >
          Cancelar
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="rounded-md bg-vpv-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          Enviar V2
        </button>
      )}
    </form>
  );
}
