import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MatchdayAccordion } from "./matchday-accordion";
import { ApiClientError, apiClient } from "@/lib/api-client";
import type {
  LineupDetailResponse,
  LineupPlayerEntry,
  MatchdayDetailResponse,
  ScoreBreakdown,
} from "@/types";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiClient: { get: vi.fn() },
}));

const get = vi.mocked(apiClient.get);

const data: MatchdayDetailResponse = {
  season_id: 1,
  number: 3,
  status: "in_progress",
  counts: true,
  stats_ok: false,
  first_match_at: null,
  matches: [],
  scores: [
    {
      participant_id: 4,
      display_name: "Azul",
      rank: null,
      total_points: 0,
      formation: "4-3-3",
      pending_players: 3,
    },
  ],
};

const ZERO: ScoreBreakdown = {
  pts_play: 0,
  pts_starter: 0,
  pts_result: 0,
  pts_clean_sheet: 0,
  pts_goals: 0,
  pts_penalty_goals: 0,
  pts_assists: 0,
  pts_penalties_saved: 0,
  pts_woodwork: 0,
  pts_penalties_won: 0,
  pts_penalties_missed: 0,
  pts_own_goals: 0,
  pts_yellow: 0,
  pts_red: 0,
  pts_pen_committed: 0,
  pts_marca: 0,
  pts_as: 0,
  pts_total: 0,
};

const player = (
  player_id: number,
  player_name: string,
  score_breakdown: ScoreBreakdown | null,
): LineupPlayerEntry => ({
  display_order: player_id,
  position_slot: "POR",
  player_id,
  player_name,
  photo_path: null,
  team_name: "Norte",
  points: 0,
  score_breakdown,
});

const lineup = (players: LineupPlayerEntry[] = []): LineupDetailResponse => ({
  participant_id: 4,
  display_name: "Azul",
  matchday_number: 3,
  formation: "4-3-3",
  total_points: 0,
  players,
  bench: [],
});

const refusal = (status: number) =>
  new ApiClientError(status, { message: "x" } as ConstructorParameters<typeof ApiClientError>[1]);

const openAzul = () => fireEvent.click(screen.getByRole("button", { name: /Azul/ }));

beforeEach(() => get.mockReset());

describe("matchday comparison", () => {
  it("says what is pending and does not present provisional scores as final", () => {
    render(<MatchdayAccordion data={data} seasonId={1} />);
    expect(screen.getByText(/pendientes de puntuar/)).toBeInTheDocument();
    expect(screen.getByText(/Provisional/)).toBeInTheDocument();
    expect(screen.queryByText("Jornada actual")).not.toBeInTheDocument();
  });

  it("reads a closed matchday as final, whether scraped or migrated", () => {
    const { rerender } = render(
      <MatchdayAccordion data={{ ...data, status: "finished", stats_ok: true }} seasonId={1} />,
    );
    expect(screen.getByText("Resultados finales")).toBeInTheDocument();
    rerender(<MatchdayAccordion data={{ ...data, status: "completed" }} seasonId={1} />);
    expect(screen.getByText("Resultados finales")).toBeInTheDocument();
    rerender(<MatchdayAccordion data={{ ...data, status: "finished" }} seasonId={1} />);
    expect(screen.getByText(/Provisional/)).toBeInTheDocument();
  });

  it("marks your row and gives each rival's difference to you", () => {
    const two = {
      ...data,
      scores: [
        { ...data.scores[0], participant_id: 5, display_name: "Rojo", total_points: 25 },
        { ...data.scores[0], total_points: 20 },
      ],
    };
    render(<MatchdayAccordion data={two} seasonId={1} participantId={4} />);
    expect(screen.getByRole("button", { name: /Azul/ })).toHaveTextContent("Tú");
    expect(screen.getByRole("button", { name: /Rojo/ })).not.toHaveTextContent("Tú");
    expect(screen.getByRole("button", { name: /Rojo/ })).toHaveTextContent("+5");
  });
});

describe("opening a participant", () => {
  it("shows a missing breakdown as not available, not as a player who did not play", async () => {
    get.mockResolvedValue(lineup([player(1, "Portero", null)]));
    render(<MatchdayAccordion data={data} seasonId={1} />);
    openAzul();
    expect(await screen.findByText("Sin desglose disponible")).toBeInTheDocument();
    expect(screen.queryByText(/no jugó/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Azul/ })).toHaveAttribute("aria-expanded", "true");
  });

  it("still says who did not play when the breakdown is there", async () => {
    get.mockResolvedValue(
      lineup([player(1, "Suplente", ZERO), player(2, "Titular", { ...ZERO, pts_play: 1 })]),
    );
    render(<MatchdayAccordion data={data} seasonId={1} />);
    openAzul();
    expect(await screen.findByText(/no jugó/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Suplente/ })).toHaveTextContent("no jugó");
    expect(screen.getByRole("button", { name: /Titular/ })).not.toHaveTextContent("no jugó");
  });

  it("explains a rival's lineup hidden until the deadline instead of offering a retry", async () => {
    get.mockRejectedValueOnce(refusal(403));
    render(<MatchdayAccordion data={data} seasonId={1} />);
    openAzul();
    expect(await screen.findByText(/se verá cuando cierre el plazo/)).toBeInTheDocument();
    expect(screen.queryByText(/No se pudo cargar/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
  });

  it("asks again when reopened, so a lineup that became public shows", async () => {
    get.mockRejectedValueOnce(refusal(403)).mockResolvedValueOnce(lineup());
    render(<MatchdayAccordion data={data} seasonId={1} />);
    openAzul();
    await screen.findByText(/se verá cuando cierre el plazo/);
    openAzul();
    openAzul();
    expect(await screen.findByText("Total")).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("offers a retry when the lineup could not be loaded", async () => {
    get.mockRejectedValueOnce(refusal(500)).mockResolvedValueOnce(lineup());
    render(<MatchdayAccordion data={data} seasonId={1} />);
    openAzul();
    expect(await screen.findByText(/No se pudo cargar la plantilla/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Total")).toBeInTheDocument();
  });

  it("stays open and reloads on refresh, and the link keeps the season", async () => {
    get.mockResolvedValue(lineup());
    const { rerender } = render(<MatchdayAccordion data={data} seasonId={1} refreshKey={0} />);
    expect(screen.getByRole("link", { name: /Ver completa/ })).toHaveAttribute(
      "href",
      "/jornadas/3?season=1",
    );
    openAzul();
    await screen.findByText("Total");
    rerender(<MatchdayAccordion data={data} seasonId={1} refreshKey={1} />);
    expect(screen.getByRole("button", { name: /Azul/ })).toHaveAttribute("aria-expanded", "true");
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Total")).toBeInTheDocument();
  });
});

describe("what each place pays", () => {
  const ranked: MatchdayDetailResponse = {
    ...data,
    scores: [
      { ...data.scores[0], participant_id: 1, display_name: "Primero", rank: 1, total_points: 50 },
      { ...data.scores[0], participant_id: 2, display_name: "Segundo", rank: 2, total_points: 30 },
      { ...data.scores[0], participant_id: 3, display_name: "Tercero", rank: 2, total_points: 30 },
    ],
  };
  const RULES = { 1: 0, 2: 1, 3: 2 };

  it("shows it on each row, a tie paying what the worse place pays", () => {
    render(<MatchdayAccordion data={ranked} seasonId={1} weeklyRules={RULES} />);
    expect(screen.getByRole("button", { name: /Primero/ })).not.toHaveTextContent("€");
    expect(screen.getByRole("button", { name: /Segundo/ })).toHaveTextContent("2 €");
    expect(screen.getByRole("button", { name: /Tercero/ })).toHaveTextContent("2 €");
  });

  it("shows nothing for a matchday that does not count", () => {
    render(
      <MatchdayAccordion data={{ ...ranked, counts: false }} seasonId={1} weeklyRules={RULES} />,
    );
    expect(screen.queryByText(/€/)).not.toBeInTheDocument();
  });

  it("shows nothing in a season without weekly payments", () => {
    render(<MatchdayAccordion data={ranked} seasonId={1} />);
    expect(screen.queryByText(/€/)).not.toBeInTheDocument();
  });

  it("shows nothing before there is a ranking, when everyone is still tied", () => {
    const unranked = {
      ...ranked,
      scores: ranked.scores.map((s) => ({ ...s, rank: null, total_points: 0 })),
    };
    render(<MatchdayAccordion data={unranked} seasonId={1} weeklyRules={RULES} />);
    expect(screen.queryByText(/€/)).not.toBeInTheDocument();
  });
});
