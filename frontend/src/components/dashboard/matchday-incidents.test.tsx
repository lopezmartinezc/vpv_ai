import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RankingsResponse } from "@/types";
import { MatchdayIncidents } from "./matchday-incidents";

const props = { seasonId: 7, matchdayNumber: 4, enabled: true };
const response = (seasonId = 7): RankingsResponse => ({
  season_id: seasonId,
  burger: {
    season_id: seasonId,
    entries: [
      {
        participant_id: 1,
        display_name: "Rival sintético",
        total: 82,
        goals: [
          {
            matchday_number: 3,
            player_id: 10,
            player_name: "Gol antiguo",
            team_name: "Equipo ficticio",
            goals: 80,
          },
          {
            matchday_number: 4,
            player_id: 11,
            player_name: "Gol actual",
            team_name: "Equipo ficticio",
            goals: 2,
          },
        ],
      },
    ],
  },
  bench: {
    season_id: seasonId,
    entries: [
      {
        participant_id: 2,
        display_name: "Otro rival sintético",
        total: 2,
        players: [
          {
            matchday_number: 3,
            player_id: 20,
            player_name: "Ausencia antigua",
            team_name: "Equipo ficticio",
            position: "DEF",
          },
          {
            matchday_number: 4,
            player_id: 21,
            player_name: "Ausencia actual",
            team_name: "Equipo ficticio",
            position: "DEF",
          },
        ],
      },
    ],
  },
});
const ok = (body: RankingsResponse) => new Response(JSON.stringify(body), { status: 200 });
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("MatchdayIncidents with real useFetch and API client", () => {
  it("does not request or expose rankings before enabled", () => {
    render(<MatchdayIncidents {...props} enabled={false} />);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText(/cuando cierre el plazo/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Ver rankings" });
    expect(link).toHaveAttribute("href", "/ranking?season=7");
    link.focus();
    expect(link).toHaveFocus();
  });

  it("shows loading, selected-matchday events and never seasonal totals", async () => {
    fetchMock.mockResolvedValueOnce(ok(response()));
    render(<MatchdayIncidents {...props} />);
    expect(screen.getByRole("status")).toHaveTextContent("Cargando");
    expect(await screen.findByText(/Gol actual/)).toHaveTextContent("2 goles");
    expect(screen.getByText(/Ausencia actual/)).toBeInTheDocument();
    expect(screen.queryByText(/Gol antiguo|Ausencia antigua|82/)).not.toBeInTheDocument();
    expect(screen.getByText(/estadísticas confirmadas/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/rankings/7",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("shows explicit empty state when only other matchdays have events", async () => {
    fetchMock.mockResolvedValueOnce(ok(response()));
    render(<MatchdayIncidents {...props} matchdayNumber={9} />);
    expect(await screen.findByText(/Sin goles fuera del once registrados/)).toBeInTheDocument();
    expect(screen.getByText(/Sin alineados sin minutos registrados/)).toBeInTheDocument();
  });

  it("retries HTTP failures with a focusable button and new loading state", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response("{}", { status: 500 }))
      .mockResolvedValueOnce(ok(response()));
    render(<MatchdayIncidents {...props} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudieron cargar");
    const retry = screen.getByRole("button", { name: "Reintentar" });
    retry.focus();
    expect(retry).toHaveFocus();
    fireEvent.click(retry);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText(/Gol actual/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("hides old results immediately when disabled and requests fresh data on reopening", async () => {
    fetchMock.mockImplementation(async () => ok(response()));
    const { rerender } = render(<MatchdayIncidents {...props} />);
    await screen.findByText(/Gol actual/);
    rerender(<MatchdayIncidents {...props} enabled={false} />);
    expect(screen.queryByText(/Gol actual/)).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    rerender(<MatchdayIncidents {...props} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    await screen.findByText(/Gol actual/);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("cannot display a late response from the previous season", async () => {
    let resolveOld!: (value: Response) => void;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    );
    fetchMock.mockResolvedValueOnce(
      ok({
        season_id: 8,
        burger: { season_id: 8, entries: [] },
        bench: { season_id: 8, entries: [] },
      }),
    );
    const { rerender } = render(<MatchdayIncidents {...props} />);
    rerender(<MatchdayIncidents {...props} seasonId={8} />);
    await screen.findByText(/Sin goles fuera del once registrados/);
    await act(async () => {
      resolveOld(ok(response()));
    });
    expect(screen.queryByText(/Gol actual/)).not.toBeInTheDocument();
  });

  it("fails closed on a mismatched season response", async () => {
    fetchMock.mockResolvedValueOnce(ok(response(8)));
    render(<MatchdayIncidents {...props} />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(/Gol actual/)).not.toBeInTheDocument();
  });

  it("refreshes events when matchday or refresh key changes", async () => {
    fetchMock.mockImplementation(async () => ok(response()));
    const { rerender } = render(<MatchdayIncidents {...props} />);
    await screen.findByText(/Gol actual/);
    rerender(<MatchdayIncidents {...props} matchdayNumber={3} />);
    expect(screen.queryByText(/Gol actual/)).not.toBeInTheDocument();
    await screen.findByText(/Gol antiguo/);
    rerender(<MatchdayIncidents {...props} matchdayNumber={3} refreshKey={1} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await screen.findByText(/Gol antiguo/);
  });
});
