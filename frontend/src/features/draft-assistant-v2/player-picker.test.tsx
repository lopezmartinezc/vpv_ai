import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PlayerPicker, matchPlayers } from "./player-picker";

const players = [
  { player_id: 1, display_name: "Pedri González", position: "MED", team_name: "Barcelona", priority: 448 },
  { player_id: 2, display_name: "Pedro Porro", position: "DEF", team_name: "Tottenham", priority: 300 },
  { player_id: 3, display_name: "Vinícius", position: "DEL", team_name: "Real Madrid", priority: 460 },
  { player_id: 4, display_name: "Dani Vivian", position: "DEF", team_name: "Athletic", priority: 390 },
];

describe("matchPlayers", () => {
  it("needs two characters before it proposes anything", () => {
    expect(matchPlayers(players, "p", [])).toEqual([]);
  });
  it("matches on name or team, best Prioridad first", () => {
    expect(matchPlayers(players, "ped", []).map((p) => p.player_id)).toEqual([1, 2]);
    expect(matchPlayers(players, "madrid", []).map((p) => p.player_id)).toEqual([3]);
  });
  it("never proposes someone already selected", () => {
    expect(matchPlayers(players, "ped", [1]).map((p) => p.player_id)).toEqual([2]);
  });
});

describe("PlayerPicker", () => {
  it("adds the clicked result and shows it as a chip", () => {
    const onChange = vi.fn();
    render(<PlayerPicker players={players} selected={[]} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Buscar jugador para comparar"), { target: { value: "viv" } });
    // The handler lives on the button inside the option (mousedown, so the
    // input's blur cannot close the list first).
    fireEvent.mouseDown(within(screen.getByRole("option")).getByRole("button"));
    expect(onChange).toHaveBeenCalledWith([4]);
  });

  it("Enter takes the first result", () => {
    const onChange = vi.fn();
    render(<PlayerPicker players={players} selected={[]} onChange={onChange} />);
    const input = screen.getByLabelText("Buscar jugador para comparar");
    fireEvent.change(input, { target: { value: "ped" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith([1]);
  });

  it("stops at three and says so", () => {
    render(<PlayerPicker players={players} selected={[1, 2, 3]} onChange={vi.fn()} />);
    const input = screen.getByLabelText("Buscar jugador para comparar");
    expect(input).toBeDisabled();
    expect(screen.getByText("Comparar (3/3)")).toBeInTheDocument();
  });

  it("a chip removes its player", () => {
    const onChange = vi.fn();
    render(<PlayerPicker players={players} selected={[1, 3]} onChange={onChange} />);
    fireEvent.click(screen.getAllByTitle("Quitar de la comparación")[0]);
    expect(onChange).toHaveBeenCalledWith([3]);
  });
});
