"use client";

/**
 * Which model estimates how much of the season a player will feature in.
 *
 * `historico` is what the board has always done: games over that season's
 * matchdays. `mixto` blends in this season's minutes at his own position and
 * club, which is what separates a starter from a man who comes on for the last
 * ten minutes every week. Backtested on held-out seasons, 0.655 -> 0.730.
 *
 * Participation multiplies into projected rest-of-season points and therefore
 * into Prioridad, so switching reorders the whole board. That is why the
 * default stays `historico` and the choice is a toggle: going back is a click,
 * not a deploy.
 */

export type ParticipationModel = "historico" | "mixto";

export const PARTICIPATION_DEFAULT: ParticipationModel = "historico";

export const PARTICIPATION_LABELS: Record<ParticipationModel, string> = {
  historico: "Histórico",
  mixto: "Mixto",
};

export const PARTICIPATION_HELP: Record<ParticipationModel, string> = {
  historico:
    "Participación = partidos jugados / jornadas de esa temporada. Es el modelo de siempre.",
  mixto:
    "Mezcla el histórico con lo que va de temporada, sobre todo los minutos que le da su equipo en su posición. Distingue al titular del que sale diez minutos cada semana (acierto 0,66 → 0,73 en temporadas de prueba).",
};

import { useSyncExternalStore } from "react";

const STORAGE_KEY = "vpv.participationModel";

export function isParticipationModel(v: unknown): v is ParticipationModel {
  return v === "historico" || v === "mixto";
}

/** Reads the stored choice; falls back to the default on anything unexpected. */
export function readParticipationModel(): ParticipationModel {
  if (typeof window === "undefined") return PARTICIPATION_DEFAULT;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isParticipationModel(stored) ? stored : PARTICIPATION_DEFAULT;
  } catch {
    return PARTICIPATION_DEFAULT;
  }
}

export function writeParticipationModel(model: ParticipationModel): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, model);
  } catch {
    // Private browsing or blocked storage: the choice just won't survive a
    // reload, which is not worth breaking the draft over.
  }
}

/** `?participacion=` for the board endpoints. Omitted when it's the default,
 *  so the request stays byte-identical to what it was before this existed. */
export function participationQuery(model: ParticipationModel): string {
  return model === PARTICIPATION_DEFAULT ? "" : `?participacion=${model}`;
}

// --- shared store -----------------------------------------------------------
// Both boards read the same choice, and the stats tab and the live draft are
// open side by side often enough that they should agree. A store also keeps
// the localStorage read out of an effect, so the server pass and the first
// client pass render the same thing and React swaps in the stored value on
// hydration by itself.

type Listener = () => void;

let cached: ParticipationModel | null = null;
const listeners = new Set<Listener>();

function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): ParticipationModel {
  if (cached === null) cached = readParticipationModel();
  return cached;
}

function getServerSnapshot(): ParticipationModel {
  return PARTICIPATION_DEFAULT;
}

export function setParticipationModel(model: ParticipationModel): void {
  if (cached === model) return;
  cached = model;
  writeParticipationModel(model);
  for (const listener of listeners) listener();
}

/** The current model and a setter that persists it. */
export function useParticipationModel(): [ParticipationModel, (m: ParticipationModel) => void] {
  const model = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return [model, setParticipationModel];
}
