"use client";

import type { JSX } from "react";

export interface ProposedPlayer {
  player_id: number;
  name: string;
  position: string;
}

/** An eleven the chat proposes, already checked by the server. */
export interface LineupProposal {
  formation: string;
  players: ProposedPlayer[];
  entering: string[];
  leaving: string[];
  basis: string;
}

export function isLineupProposal(value: unknown): value is LineupProposal {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.formation === "string" &&
    Array.isArray(v.players) &&
    Array.isArray(v.entering) &&
    Array.isArray(v.leaving)
  );
}

function names(list: string[]): string {
  return list.length ? list.join(", ") : "nadie";
}

/**
 * "Salen A y B → entran C y D · Aplicar al borrador · Descartar". Applying
 * only changes the selection on screen; sending is still the user's click.
 */
export function ProposalCard({
  proposal,
  applied,
  onApply,
  onUndo,
  onDiscard,
}: {
  proposal: LineupProposal;
  applied: boolean;
  onApply: () => void;
  onUndo: () => void;
  onDiscard: () => void;
}): JSX.Element {
  return (
    <div
      role="region"
      aria-label="Propuesta del asistente"
      className="rounded-lg border border-vpv-accent/30 bg-vpv-accent/5 px-3 py-2 text-xs"
    >
      <p className="font-semibold text-vpv-text">
        Propuesta {proposal.formation}
        {applied && <span className="ml-2 font-normal text-vpv-success">aplicada al borrador</span>}
      </p>
      <p className="mt-1 text-vpv-text-muted">
        Salen <span className="text-vpv-text">{names(proposal.leaving)}</span>
        {" → "}
        entran <span className="text-vpv-text">{names(proposal.entering)}</span>
      </p>
      {proposal.basis && <p className="mt-1 text-vpv-text-muted">{proposal.basis}</p>}
      <div className="mt-2 flex gap-2">
        {applied ? (
          <button
            type="button"
            onClick={onUndo}
            className="rounded-md border border-vpv-border px-2.5 py-1 font-medium text-vpv-text hover:bg-vpv-card"
          >
            Deshacer
          </button>
        ) : (
          <button
            type="button"
            onClick={onApply}
            className="rounded-md bg-vpv-accent px-2.5 py-1 font-medium text-white hover:bg-vpv-accent/90"
          >
            Aplicar al borrador
          </button>
        )}
        <button
          type="button"
          onClick={onDiscard}
          className="rounded-md px-2.5 py-1 font-medium text-vpv-text-muted hover:text-vpv-text"
        >
          Descartar
        </button>
      </div>
    </div>
  );
}
