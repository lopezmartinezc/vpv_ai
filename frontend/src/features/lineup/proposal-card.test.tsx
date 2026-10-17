import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProposalCard, isLineupProposal, type LineupProposal } from "./proposal-card";

const PROPOSAL: LineupProposal = {
  formation: "1-4-3-3",
  players: [{ player_id: 1, name: "Joan Garcia", position: "POR" }],
  entering: ["Puado"],
  leaving: ["Raphinha"],
  basis: "Cambio propuesto en el chat.",
};

afterEach(cleanup);

describe("isLineupProposal", () => {
  it.each([null, undefined, "x", {}, { formation: "1-4-3-3" }])("rejects %s", (v) => {
    expect(isLineupProposal(v)).toBe(false);
  });
  it("accepts the server's shape", () => {
    expect(isLineupProposal(PROPOSAL)).toBe(true);
  });
});

describe("ProposalCard", () => {
  it("says who leaves and enters, and offers to apply", () => {
    const onApply = vi.fn();
    render(
      <ProposalCard proposal={PROPOSAL} applied={false} onApply={onApply} onUndo={vi.fn()} onDiscard={vi.fn()} />,
    );
    expect(screen.getByRole("region", { name: "Propuesta del asistente" })).toHaveTextContent(
      "Salen Raphinha → entran Puado",
    );
    fireEvent.click(screen.getByRole("button", { name: "Aplicar al borrador" }));
    expect(onApply).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Deshacer" })).not.toBeInTheDocument();
  });

  it("offers to undo once applied, and to discard always", () => {
    const onUndo = vi.fn();
    const onDiscard = vi.fn();
    render(
      <ProposalCard proposal={PROPOSAL} applied onApply={vi.fn()} onUndo={onUndo} onDiscard={onDiscard} />,
    );
    expect(screen.getByText("aplicada al borrador")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Deshacer" }));
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
    expect(onUndo).toHaveBeenCalledOnce();
    expect(onDiscard).toHaveBeenCalledOnce();
  });
});
