import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePathname } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { DeadlineBanner } from "./deadline-banner";

// Stable objects: a new user on every render would re-run the polling effect.
const ctx = vi.hoisted(() => ({
  auth: { user: { id: 1 } },
  season: { selectedSeason: { id: 12 } },
}));

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }));
vi.mock("@/contexts/auth-context", () => ({ useAuth: () => ctx.auth }));
vi.mock("@/contexts/season-context", () => ({ useSeason: () => ctx.season }));
vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiClient: { get: vi.fn() },
}));

const pending = { has_lineup: false, deadline_at: null, minutes_remaining: 45, matchday_number: 6 };

afterEach(() => vi.mocked(apiClient.get).mockReset());

describe("DeadlineBanner", () => {
  it("reminds you of a missing lineup in its last two hours, anywhere but the home", async () => {
    vi.mocked(usePathname).mockReturnValue("/jornadas");
    vi.mocked(apiClient.get).mockResolvedValue(pending);
    render(<DeadlineBanner />);
    expect(await screen.findByText(/No has enviado alineacion para J6/)).toBeInTheDocument();
  });

  it("goes away as soon as you open the home", async () => {
    vi.mocked(usePathname).mockReturnValue("/jornadas");
    vi.mocked(apiClient.get).mockResolvedValue(pending);
    const { rerender } = render(<DeadlineBanner />);
    await screen.findByText(/No has enviado alineacion/);
    vi.mocked(usePathname).mockReturnValue("/");
    rerender(<DeadlineBanner />);
    expect(screen.queryByText(/No has enviado alineacion/)).not.toBeInTheDocument();
  });

  it("stays out of the home, which has its own lineup strip, and asks nothing", async () => {
    vi.mocked(usePathname).mockReturnValue("/");
    vi.mocked(apiClient.get).mockResolvedValue(pending);
    const { container } = render(<DeadlineBanner />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container).toBeEmptyDOMElement();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});
