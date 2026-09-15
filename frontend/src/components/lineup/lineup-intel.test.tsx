import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  LineupAdminBar,
  SourceBadges,
  SuggestionPanel,
  applySuggestion,
  type SourceReading,
  type SuggestionResponse,
} from "./lineup-intel";
import { ApiClientError, apiClient } from "@/lib/api-client";
import type { SquadPlayerEntry } from "@/types";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);

afterEach(() => {
  get.mockReset();
  post.mockReset();
});

const reading = (over: Partial<SourceReading>): SourceReading => ({
  source: "futbolfantasy",
  probability: 70,
  previous_probability: null,
  starter: true,
  status: null,
  note: null,
  fetched_at: "2026-09-19T10:00:00Z",
  ...over,
});

const squadPlayer = (player_id: number, display_name: string): SquadPlayerEntry => ({
  player_id,
  display_name,
  photo_path: null,
  position: "DEL",
  team_name: "Barcelona",
  season_points: 10,
  recent_form: null,
});

const suggestion: SuggestionResponse = {
  season_id: 12,
  matchday_number: 6,
  formation: "1-4-3-3",
  total: 48.3,
  eleven: [
    {
      player_id: 2,
      name: "Raphinha",
      position: "DEL",
      team_name: "Barcelona",
      value: 5.25,
      xpts_if_plays: 7,
      play_prob: 0.75,
      basis: "alineaciones probables (AF 70 % · FF 80 %)",
    },
    {
      player_id: 9,
      name: "Nadie",
      position: "DEL",
      team_name: "Racing",
      value: 0,
      xpts_if_plays: null,
      play_prob: 0,
      basis: "sin partido ni prevision esta jornada",
    },
  ],
  bench: [],
};

describe("SourceBadges", () => {
  it("shows each source's percentage and which way it moved", () => {
    render(
      <SourceBadges
        readings={[
          reading({ probability: 70, previous_probability: 50 }),
          reading({ source: "analiticafantasy", probability: 60, previous_probability: 80 }),
        ]}
      />,
    );
    expect(screen.getByText("FF")).toBeInTheDocument();
    expect(screen.getByText("70%", { exact: false })).toBeInTheDocument();
    expect(screen.getByTitle("antes 50%")).toHaveTextContent("↑");
    expect(screen.getByTitle("antes 80%")).toHaveTextContent("↓");
  });

  it("marks the gravest state, with the report on hover", () => {
    render(
      <SourceBadges
        readings={[
          reading({ status: "duda", note: "Molestias en el pie" }),
          reading({ source: "analiticafantasy", status: "lesionado", note: "Rotura" }),
        ]}
      />,
    );
    const chip = screen.getByText("Lesionado");
    expect(chip.getAttribute("title")).toContain("FF: Molestias en el pie");
    expect(chip.getAttribute("title")).toContain("AF: Rotura");
    expect(screen.queryByText("Duda")).not.toBeInTheDocument();
  });

  it("renders nothing without readings", () => {
    const { container } = render(<SourceBadges readings={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("applySuggestion", () => {
  it("picks the proposed players from the squad, in order, skipping strangers", () => {
    const squad = [squadPlayer(1, "Pedri"), squadPlayer(2, "Raphinha")];
    expect(applySuggestion(squad, suggestion).map((p) => p.display_name)).toEqual(["Raphinha"]);
  });
});

describe("LineupAdminBar", () => {
  const bar = (over: Partial<Parameters<typeof LineupAdminBar>[0]> = {}) => {
    const props = {
      seasonId: 12,
      matchday: 6,
      updatedAt: null,
      onRefreshed: vi.fn(),
      onSuggestion: vi.fn(),
      ...over,
    };
    render(<LineupAdminBar {...props} />);
    return props;
  };

  it("proposes an eleven without sending any lineup", async () => {
    get.mockResolvedValue(suggestion);
    const props = bar();
    fireEvent.click(screen.getByText("Proponer once"));
    await waitFor(() => expect(props.onSuggestion).toHaveBeenCalledWith(suggestion));
    expect(get).toHaveBeenCalledWith("/lineup-assistant/12/6/suggestion");
    expect(post).not.toHaveBeenCalled();
  });

  it("refreshes the sources and says when one had trouble", async () => {
    post.mockResolvedValue({
      sources: {
        futbolfantasy: { rows: 500, matched: 480, news: 90, errors: [] },
        analiticafantasy: { rows: 0, matched: 0, news: 0, errors: ["jornada: 404"] },
      },
    });
    const props = bar();
    fireEvent.click(screen.getByText("Actualizar"));
    await waitFor(() => expect(props.onRefreshed).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith("/lineup-intel/12/6/refresh", {});
    expect(screen.getByRole("status")).toHaveTextContent("Con avisos: AF (1).");
  });

  it("shows the reason when a refresh is refused", async () => {
    post.mockRejectedValue(
      new ApiClientError(422, {
        code: "BUSINESS_RULE",
        message: "Se ha actualizado hace poco. Prueba dentro de 7 min.",
      }),
    );
    const props = bar({ updatedAt: "2026-09-19T10:00:00Z" });
    fireEvent.click(screen.getByText("Actualizar"));
    expect(await screen.findByRole("status")).toHaveTextContent("Prueba dentro de 7 min.");
    expect(props.onRefreshed).not.toHaveBeenCalled();
    expect(screen.getByText(/leídas el/)).toBeInTheDocument();
  });
});

describe("SuggestionPanel", () => {
  it("explains each choice as points if he plays times the chance he plays", () => {
    render(<SuggestionPanel suggestion={suggestion} onClose={vi.fn()} />);
    expect(screen.getByText(/Once propuesto 1-4-3-3/)).toBeInTheDocument();
    expect(screen.getByText(/5\.3 = 7\.0 si juega × 75%/)).toBeInTheDocument();
    expect(screen.getByText(/sin previsión/)).toBeInTheDocument();
  });
});
