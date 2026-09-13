import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

// The season being viewed: 12. Anything else is what the link must not keep.
vi.mock("@/contexts/season-context", () => ({
  useSeason: () => ({ selectedSeason: { id: 12 } }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { SeasonLink } from "@/components/ui/season-link";

const hrefOf = (name: string) => screen.getByRole("link", { name }).getAttribute("href");

describe("SeasonLink", () => {
  it("carries the season being viewed to a season page", () => {
    render(<SeasonLink href="/clasificacion">Clasificación</SeasonLink>);
    expect(hrefOf("Clasificación")).toBe("/clasificacion?season=12");
  });

  it("leaves a route that belongs to no season untouched", () => {
    render(<SeasonLink href="/perfil">Mi perfil</SeasonLink>);
    expect(hrefOf("Mi perfil")).toBe("/perfil");
  });

  it("passes the rest of the props through", () => {
    render(
      <SeasonLink href="/jornadas" className="x" aria-current="page">
        Jornadas
      </SeasonLink>,
    );
    const link = screen.getByRole("link", { name: "Jornadas" });
    expect(link.getAttribute("class")).toBe("x");
    expect(link.getAttribute("aria-current")).toBe("page");
  });
});
