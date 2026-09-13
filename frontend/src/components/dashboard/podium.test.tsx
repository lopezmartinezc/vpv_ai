import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Podium } from "./podium";
import type { StandingEntry } from "@/types";

const entry = (participant_id: number, rank: number, display_name: string, total_points: number) =>
  ({ participant_id, rank, display_name, total_points }) as StandingEntry;

const entries = [entry(4, 1, "Azul", 120), entry(7, 2, "Rojo", 101)];

describe("Podium", () => {
  it("links to the full table of the season it shows", () => {
    render(<Podium entries={entries} seasonId={12} />);
    expect(screen.getByRole("link", { name: /Ver clasificación completa/ })).toHaveAttribute(
      "href",
      "/clasificacion?season=12",
    );
  });

  it("marks your team, and only yours", () => {
    render(<Podium entries={entries} participantId={7} seasonId={12} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows[1]).toHaveAttribute("data-you", "true");
    expect(rows[1]).toHaveTextContent("Mi equipo");
    expect(rows[0]).toHaveAttribute("data-you", "false");
    expect(rows[0]).not.toHaveTextContent("Mi equipo");
  });

  it("marks nobody when you are not in the league", () => {
    render(<Podium entries={entries} seasonId={12} />);
    expect(screen.queryByText(/Mi equipo/)).not.toBeInTheDocument();
  });

  it("renders nothing without standings", () => {
    const { container } = render(<Podium entries={[]} seasonId={12} />);
    expect(container).toBeEmptyDOMElement();
  });
});
