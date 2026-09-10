"use client";
import { useMemo, useState, type ReactElement } from "react";
import type { PanelProps } from "./contracts";

export const MAX_COMPARED = 3;
const MIN_QUERY = 2;
const MAX_RESULTS = 8;

type Row = PanelProps["players"][number];

/** Name or team match, best Prioridad first — the same order the board uses,
 *  so the first result is the one you most likely meant. */
export function matchPlayers(players: readonly Row[], query: string, exclude: readonly number[]): Row[] {
  const q = query.trim().toLowerCase();
  if (q.length < MIN_QUERY) return [];
  return players
    .filter((p) => !exclude.includes(p.player_id))
    .filter((p) => p.display_name.toLowerCase().includes(q) || p.team_name.toLowerCase().includes(q))
    .sort((a, b) => (b.priority ?? -1e9) - (a.priority ?? -1e9))
    .slice(0, MAX_RESULTS);
}

/**
 * Pick up to three players to compare, by typing.
 *
 * Replaces a native multi-select listing every player on the board — five
 * hundred rows to scroll, three to hold down Ctrl over — with the thing people
 * actually do: type a few letters, click the name. Selected players sit above
 * as chips that remove with a click.
 */
export function PlayerPicker({
  players,
  selected,
  onChange,
  disabled = false,
}: {
  players: PanelProps["players"];
  selected: number[];
  onChange: (ids: number[]) => void;
  disabled?: boolean;
}): ReactElement {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const full = selected.length >= MAX_COMPARED;
  const results = useMemo(() => (full ? [] : matchPlayers(players, query, selected)), [players, query, selected, full]);
  const byId = useMemo(() => new Map(players.map((p) => [p.player_id, p])), [players]);

  const add = (id: number): void => {
    if (full || selected.includes(id)) return;
    onChange([...selected, id]);
    setQuery("");
    setOpen(false);
  };
  const remove = (id: number): void => onChange(selected.filter((x) => x !== id));

  return (
    <div className="relative">
      <span className="block text-[10px] font-medium uppercase tracking-wide text-vpv-text-muted">
        Comparar ({selected.length}/{MAX_COMPARED})
      </span>

      {selected.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1" aria-label="Jugadores a comparar">
          {selected.map((id) => {
            const p = byId.get(id);
            return (
              <button
                key={id}
                type="button"
                disabled={disabled}
                title="Quitar de la comparación"
                onClick={() => remove(id)}
                className="rounded-full border border-vpv-accent/40 bg-vpv-accent/10 px-2 py-0.5 text-[10px] text-vpv-text hover:border-vpv-accent disabled:opacity-50"
              >
                {p?.display_name ?? `#${id}`}
                {p && <span className="ml-1 text-vpv-text-muted">{p.position}</span>} ×
              </button>
            );
          })}
        </div>
      )}

      <input
        type="search"
        aria-label="Buscar jugador para comparar"
        role="combobox"
        aria-expanded={open && results.length > 0}
        aria-controls="v2-picker-results"
        aria-autocomplete="list"
        value={query}
        disabled={disabled || full}
        placeholder={full ? "Ya hay tres seleccionados" : "Escribe un nombre o equipo…"}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && results[0]) {
            e.preventDefault();
            add(results[0].player_id);
          }
          if (e.key === "Escape") {
            setQuery("");
            setOpen(false);
          }
        }}
        className="mt-1 w-full rounded-md border border-vpv-card-border bg-vpv-bg px-2 py-1.5 text-xs text-vpv-text placeholder:text-vpv-text-muted disabled:opacity-50"
      />

      {open && results.length > 0 && (
        <ul
          id="v2-picker-results"
          role="listbox"
          className="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-vpv-card-border bg-vpv-card shadow-lg"
        >
          {results.map((p, i) => (
            <li key={p.player_id} role="option" aria-selected={i === 0}>
              <button
                type="button"
                // mousedown, not click: the input blurs (and closes the list) before a click lands.
                onMouseDown={(e) => {
                  e.preventDefault();
                  add(p.player_id);
                }}
                className={`flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left text-xs hover:bg-vpv-accent/10 ${
                  i === 0 ? "bg-vpv-accent/5" : ""
                }`}
              >
                <span className="truncate text-vpv-text">{p.display_name}</span>
                <span className="shrink-0 text-[10px] text-vpv-text-muted">
                  {p.position} · {p.team_name}
                  {p.priority != null && <span className="ml-1 tabular-nums text-vpv-text">{p.priority.toFixed(0)}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
