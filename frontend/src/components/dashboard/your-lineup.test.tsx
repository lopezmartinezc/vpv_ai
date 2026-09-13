import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { YourLineup } from "./your-lineup";
import { ApiClientError, apiClient } from "@/lib/api-client";
import type { LineupDetailResponse, LineupPlayerEntry, ScoreBreakdown } from "@/types";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiClient: { get: vi.fn() },
}));

const get = vi.mocked(apiClient.get);

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
  points: number,
  score_breakdown: ScoreBreakdown | null,
): LineupPlayerEntry => ({
  display_order: player_id,
  position_slot: "DEL",
  player_id,
  player_name,
  photo_path: null,
  team_name: "Norte",
  points,
  score_breakdown,
});

const lineup: LineupDetailResponse = {
  participant_id: 7,
  display_name: "Ana",
  matchday_number: 5,
  formation: "1-4-3-3",
  total_points: 12,
  players: [
    player(1, "Goleador", 12, { ...ZERO, pts_play: 2, pts_goals: 10 }),
    player(2, "Pendiente", 0, null),
    player(3, "Suplente", 0, ZERO),
  ],
  bench: [
    {
      player_id: 4,
      player_name: "Reserva",
      photo_path: null,
      position: "MED",
      team_name: "Sur",
      matchday_points: 3,
      score_breakdown: { ...ZERO, pts_play: 1 },
    },
  ],
};

const refusal = (status: number) =>
  new ApiClientError(status, { message: "x" } as ConstructorParameters<typeof ApiClientError>[1]);

const props = { seasonId: 1, matchdayNumber: 5, participantId: 7 };

afterEach(() => get.mockReset());

describe("YourLineup", () => {
  it("shows your eleven with the points so far, open without a click", async () => {
    get.mockResolvedValueOnce(lineup);
    render(<YourLineup {...props} />);
    const card = await screen.findByRole("region", { name: "Tu once · J5" });
    expect(card).toHaveTextContent("12 pts");
    expect(screen.getByRole("button", { name: /Goleador/ })).toHaveTextContent("12");
    expect(get).toHaveBeenCalledWith("/matchdays/1/5/lineup/7");
  });

  it("marks who is still to be scored, and tells it apart from who did not play", async () => {
    get.mockResolvedValueOnce(lineup);
    render(<YourLineup {...props} />);
    expect(await screen.findByRole("button", { name: /Pendiente/ })).toHaveTextContent(
      "pendiente de puntuar",
    );
    expect(screen.getByRole("button", { name: /Pendiente/ })).not.toHaveTextContent("no jugó");
    expect(screen.getByRole("button", { name: /Suplente/ })).toHaveTextContent("no jugó");
    expect(screen.queryByText("Sin desglose disponible")).not.toBeInTheDocument();
  });

  it("keeps the bench folded", async () => {
    get.mockResolvedValueOnce(lineup);
    render(<YourLineup {...props} />);
    const bench = (await screen.findByText(/Banquillo \(1\)/)).closest("details");
    expect(bench).not.toBeNull();
    expect(bench).not.toHaveAttribute("open");
    expect(bench).toHaveTextContent("Reserva");
  });

  it("says you fielded no side, which is not an error", async () => {
    get.mockRejectedValueOnce(refusal(404));
    render(<YourLineup {...props} />);
    expect(await screen.findByText("No alineaste en la J5.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
  });

  it("offers a retry when it could not load", async () => {
    get.mockRejectedValueOnce(refusal(500)).mockResolvedValueOnce(lineup);
    render(<YourLineup {...props} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo cargar tu once");
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("button", { name: /Goleador/ })).toBeInTheDocument();
  });

  it("reloads when the home refreshes", async () => {
    get.mockResolvedValue(lineup);
    const { rerender } = render(<YourLineup {...props} refreshKey={0} />);
    await screen.findByRole("button", { name: /Goleador/ });
    rerender(<YourLineup {...props} refreshKey={1} />);
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });
});
