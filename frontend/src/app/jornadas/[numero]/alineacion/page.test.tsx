import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Page from "./page";

const context = vi.hoisted(() => ({ user: "1", season: 1, matchday: "6" }));
vi.mock("next/navigation", () => ({ useParams: () => ({ numero: context.matchday }) }));
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ user: { id: context.user, isAdmin: true }, loading: false }),
}));
vi.mock("@/contexts/season-context", () => ({
  useSeason: () => ({ selectedSeason: { id: context.season }, loading: false }),
}));
vi.mock("@/components/ui/season-link", () => ({
  SeasonLink: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));
vi.mock("@/components/ui/pitch-view", () => ({ PitchView: () => null }));
vi.mock("@/components/ui/player-avatar", () => ({ PlayerAvatar: () => null }));
vi.mock("@/components/lineup/lineup-intel", () => ({
  LineupAdminBar: () => null,
  SourceBadges: () => null,
  SuggestionPanel: () => null,
  readingsByPlayer: () => new Map(),
  coverageByTeam: () => new Map(),
}));
vi.mock("@/components/assistant/assistant-panel", () => ({
  AssistantPanel: ({ extraBody }: { extraBody?: Record<string, unknown> }) => (
    <input aria-label="Chat draft" defaultValue="" data-draft={JSON.stringify(extraBody?.draft)} />
  ),
}));
vi.mock("@/hooks/use-fetch", () => ({
  useFetch: (path: string | null) => ({
    loading: false,
    refetch: vi.fn(),
    data: path?.endsWith("/me")
      ? {
          display_name: "Manager",
          current_lineup: null,
          lineup_deadline_min: 30,
          squad: [{ player_id: 1, display_name: "Goalkeeper", position: "POR", team_name: "Team" }],
        }
      : path === "/seasons/formations"
        ? [{ formation: "1-4-3-3", defenders: 4, midfielders: 3, forwards: 3 }]
        : path?.startsWith("/matchdays/")
          ? {
              first_match_at: "2026-10-17T16:00:00Z",
              deadline_at: "2026-10-17T13:00:00Z",
              matches: [],
            }
          : null,
  }),
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  Object.assign(context, { user: "1", season: 1, matchday: "6" });
});

describe("lineup context isolation", () => {
  it.each(["user", "season", "matchday"] as const)("resets editor and chat on %s change", (key) => {
    const view = render(<Page />);
    fireEvent.click(screen.getByRole("button", { name: /Goalkeeper/ }));
    fireEvent.change(screen.getByLabelText("Chat draft"), { target: { value: "old question" } });
    expect(screen.getByText("Selecciona exactamente 11 jugadores")).toBeInTheDocument();
    view.rerender(<Page />);
    expect(screen.getByLabelText("Chat draft")).toHaveValue("old question");
    if (key === "season") context.season = 2;
    else context[key] = "7";
    view.rerender(<Page />);
    expect(screen.queryByText("Selecciona exactamente 11 jugadores")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Chat draft")).toHaveValue("");
  });

  it("tells the chat the eleven on screen, unsent", () => {
    render(<Page />);
    const draft = () => JSON.parse(screen.getByLabelText("Chat draft").getAttribute("data-draft") ?? "null");
    expect(draft()).toEqual({ formation: null, players: [] });
    fireEvent.click(screen.getByRole("button", { name: /Goalkeeper/ }));
    expect(draft()).toEqual({ formation: null, players: [{ player_id: 1, position_slot: "POR" }] });
  });

  it("uses the effective deadline instead of kick-off minus margin", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-17T12:00:00Z"));
    render(<Page />);
    expect(screen.getByRole("status")).toHaveTextContent("Cierre en 1h 0m");
  });
});
