import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LIGA_PLAYOFF_LABEL, PlayoffDsHero } from "./playoff-ds-hero";

describe("PlayoffDsHero", () => {
  it("names the Liga's playoff after David Silva", () => {
    render(<PlayoffDsHero subtitle="2026-2027" />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("PLAYOFF DAVID SILVA");
    expect(screen.getByText("2026-2027")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(LIGA_PLAYOFF_LABEL).toBe("Playoff DS");
  });
});
