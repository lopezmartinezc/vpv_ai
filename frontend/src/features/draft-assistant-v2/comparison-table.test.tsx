import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ComparisonTable } from "./comparison-table";
import type { Card } from "./contracts";

const base: Card = {
  player_id: 1, name: "Pedri", position: "MED", team: "Barcelona", available: true,
  priority: 448, priority_base: 440, vorp: 20, participation: 0.9, available_gap: 12, marginal_gain: 12,
  avg_points: 8.1, games_played: 30, seasons_played: 4, availability: 0.95, exp_games_remaining: 28,
  is_new: false, team_changed: false, position_changed: false, tags: ["titular"], evidence_id: "player:1",
};
const rival: Card = {
  ...base, player_id: 2, name: "Xavi", priority: 430, priority_base: 430, vorp: 25, participation: 0.6,
  avg_points: 9.4, games_played: 5, seasons_played: 0, availability: 1, is_new: true, tags: [], evidence_id: "player:2",
};

describe("ComparisonTable", () => {
  it("marks the best value in each row, whoever holds it", () => {
    render(<ComparisonTable cards={[base, rival]} onSelect={vi.fn()} />);
    const prio = screen.getByRole("row", { name: /Prioridad/ });
    expect(within(prio).getByText("448")).toHaveClass("text-green-400");
    expect(within(prio).getByText("430")).not.toHaveClass("text-green-400");
    const vorp = screen.getByRole("row", { name: /VORP/ });
    expect(within(vorp).getByText("25.0")).toHaveClass("text-green-400");
  });

  it("shows confidence with its reason — the point of comparing", () => {
    render(<ComparisonTable cards={[base, rival]} onSelect={vi.fn()} />);
    const row = screen.getByRole("row", { name: /Confianza/ });
    expect(within(row).getByText("●●●")).toBeInTheDocument();
    expect(within(row).getByText("●○○")).toBeInTheDocument();
    expect(within(row).getByText(/sin histórico/)).toBeInTheDocument();
  });

  it("tolerates a card from an older backend with no comparison fields", () => {
    const old = { ...base, player_id: 3, name: "Viejo", avg_points: undefined, games_played: undefined,
      seasons_played: undefined, availability: undefined, exp_games_remaining: undefined,
      is_new: undefined, team_changed: undefined, position_changed: undefined } as Card;
    render(<ComparisonTable cards={[base, old]} onSelect={vi.fn()} />);
    const row = screen.getByRole("row", { name: /Media pts/ });
    expect(within(row).getByText("—")).toBeInTheDocument();
  });

  it("does not crown a winner when only one value is present", () => {
    const missing = { ...rival, priority: null } as Card;
    render(<ComparisonTable cards={[base, missing]} onSelect={vi.fn()} />);
    const prio = screen.getByRole("row", { name: /Prioridad/ });
    expect(within(prio).getByText("448")).not.toHaveClass("text-green-400");
  });

  it("clicking a name opens that player", () => {
    const onSelect = vi.fn();
    render(<ComparisonTable cards={[base, rival]} onSelect={onSelect} />);
    screen.getByRole("button", { name: "Xavi" }).click();
    expect(onSelect).toHaveBeenCalledWith(2);
  });
});
