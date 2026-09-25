import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LigaPlayoffHero } from "./liga-playoff-hero";
import { playoffName, playoffTitle } from "@/lib/playoff-name";

describe("LigaPlayoffHero", () => {
  it("names the Liga's playoffs DAVID SILVA Cup", () => {
    render(<LigaPlayoffHero subtitle="2026-2027" />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("DAVID SILVA Cup");
    expect(screen.getByText("2026-2027")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});

describe("playoff names", () => {
  it("calls each Liga playoff DAVID SILVA Cup and leaves tournaments alone", () => {
    expect(playoffTitle(false, "Apertura")).toBe("DAVID SILVA Cup Apertura");
    expect(playoffName(false)).toBe("DAVID SILVA Cup");
    expect(playoffTitle(true, "Playoff Mundial")).toBe("Playoff Mundial");
    expect(playoffName(true)).toBe("Playoff");
  });
});
