import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LIGA_PLAYOFF_LABEL, PlayoffDsHero } from "./playoff-ds-hero";

describe("PlayoffDsHero", () => {
  it("names the Liga's playoff after David Silva, with his badge", () => {
    render(<PlayoffDsHero subtitle="2026-2027" />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("PLAYOFF DAVID SILVA");
    expect(screen.getByAltText("Escudo del Playoff David Silva")).toBeInTheDocument();
    expect(screen.getByText("2026-2027")).toBeInTheDocument();
    expect(LIGA_PLAYOFF_LABEL).toBe("Playoff DS");
  });

  it("keeps the name when the badge is missing on the server", () => {
    render(<PlayoffDsHero />);
    fireEvent.error(screen.getByAltText("Escudo del Playoff David Silva"));
    expect(screen.queryByAltText("Escudo del Playoff David Silva")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("PLAYOFF DAVID SILVA");
  });
});
