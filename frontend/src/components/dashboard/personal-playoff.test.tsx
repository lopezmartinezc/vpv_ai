import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PersonalPlayoff } from "./personal-playoff";
import type { CompetitionMatchupsResponse, MatchupEntry } from "@/types";

const competition = {
  id: 7,
  season_id: 1,
  name: "Liga playoff",
  type: "playoff",
  status: "regular",
  config: null,
};
const matchup: MatchupEntry = {
  id: 2,
  phase: "regular",
  group_label: null,
  round_label: null,
  round_number: 1,
  matchday_id: 100,
  matchday_number: 12,
  participant_a_id: 10,
  participant_a_name: "Ana",
  participant_b_id: 20,
  participant_b_name: "Luis",
  feeder_a_id: null,
  feeder_b_id: null,
  score_a: 0,
  score_b: null,
  winner_participant_id: null,
  winner_name: null,
};
const props = { seasonId: 1, matchdayNumber: 12, participantId: 10 };
function serve(matchups: MatchupEntry[] = [matchup]) {
  return vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const body = input.endsWith("/season/1")
        ? { season_id: 1, competitions: [competition] }
        : ({ competition, matchups } satisfies CompetitionMatchupsResponse);
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PersonalPlayoff", () => {
  it("loads, faces you as side A and tells zero from not scored, without borrowing the league score", async () => {
    serve();
    render(
      <PersonalPlayoff
        {...props}
        scores={[
          {
            participant_id: 10,
            rank: 1,
            display_name: "Ana",
            total_points: 99,
            formation: null,
            pending_players: 0,
          },
        ]}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Cargando playoff");
    expect(await screen.findByText("Luis")).toBeInTheDocument();
    expect(screen.getByLabelText("Marcador del playoff")).toHaveTextContent("0 : —");
    expect(screen.queryByText("99")).not.toBeInTheDocument();
    expect(screen.getByText(/tú 0 · rival sin datos/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Ver playoffs/ });
    link.focus();
    expect(link).toHaveFocus();
    expect(link).toHaveAttribute("href", "/playoffs?season=1");
  });

  it("turns the scoreboard and the rival around for side B", async () => {
    serve([{ ...matchup, score_b: 21 }]);
    render(<PersonalPlayoff {...props} participantId={20} />);
    expect(await screen.findByText("Ana")).toBeInTheDocument();
    expect(screen.getByLabelText("Marcador del playoff")).toHaveTextContent("21 : 0");
  });

  it("shows no duel from another matchday and does not assume a bye", async () => {
    serve();
    render(<PersonalPlayoff {...props} matchdayNumber={13} />);
    expect(
      await screen.findByText("No tienes enfrentamiento asignado en esta jornada."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Luis")).not.toBeInTheDocument();
    expect(screen.queryByText(/descanso/i)).not.toBeInTheDocument();
  });

  it("tells a rival still to be decided from a missing one", async () => {
    serve([{ ...matchup, participant_b_id: null, participant_b_name: null, feeder_b_id: 9 }]);
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByText("Rival por decidir")).toBeInTheDocument();
  });

  it("asks for nothing without a participant", () => {
    serve();
    render(<PersonalPlayoff {...props} participantId={null} />);
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("says so when the season has no playoff", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ season_id: 1, competitions: [] }))),
    );
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByText("Esta temporada todavía no tiene playoff.")).toBeInTheDocument();
  });

  it("recovers from an HTTP error with the refresh button", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 500 })),
    );
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo cargar tu playoff");
    serve();
    fireEvent.click(screen.getByRole("button", { name: "Actualizar playoff" }));
    expect(await screen.findByText("Luis")).toBeInTheDocument();
  });

  it("reports a failure to load the duel itself", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) =>
        input.endsWith("/season/1")
          ? new Response(JSON.stringify({ season_id: 1, competitions: [competition] }))
          : new Response("{}", { status: 500 }),
      ),
    );
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo cargar tu enfrentamiento",
    );
  });

  it("refuses a duel that belongs to another season", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) =>
        input.endsWith("/season/1")
          ? new Response(JSON.stringify({ season_id: 1, competitions: [competition] }))
          : new Response(
              JSON.stringify({ competition: { ...competition, season_id: 2 }, matchups: [matchup] }),
            ),
      ),
    );
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo cargar tu enfrentamiento",
    );
    expect(screen.queryByText("Luis")).not.toBeInTheDocument();
  });

  it("drops the old season's duel as soon as the season changes", async () => {
    serve();
    const { rerender } = render(<PersonalPlayoff {...props} />);
    await screen.findByText("Luis");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ season_id: 2, competitions: [] }))),
    );
    rerender(<PersonalPlayoff {...props} seasonId={2} />);
    expect(screen.queryByText("Luis")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Esta temporada todavía no tiene playoff.")).toBeInTheDocument(),
    );
  });

  it("reloads both requests on refreshKey without remounting", async () => {
    serve([{ ...matchup, score_b: 1 }]);
    const { rerender } = render(<PersonalPlayoff {...props} refreshKey={0} />);
    await screen.findByText("Luis");
    expect(screen.getByText("Marcador provisional del playoff.")).toBeInTheDocument();
    serve([{ ...matchup, score_b: 7 }]);
    rerender(<PersonalPlayoff {...props} refreshKey={1} matchdayFinal />);
    await waitFor(() =>
      expect(screen.getByLabelText("Marcador del playoff")).toHaveTextContent("0 : 7"),
    );
    expect(fetch).toHaveBeenCalledWith("/api/competitions/season/1", expect.anything());
    expect(fetch).toHaveBeenCalledWith("/api/competitions/7/matchups", expect.anything());
    expect(screen.getByText(/jornada cerrada/)).toBeInTheDocument();
  });

  it("looks through every playoff of the season and finds the duel in the second", async () => {
    const second = { ...competition, id: 8, name: "Clausura" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        const body = input.endsWith("/season/1")
          ? { season_id: 1, competitions: [competition, second] }
          : input.endsWith("/7/matchups")
            ? { competition, matchups: [] }
            : { competition: second, matchups: [matchup] };
        return new Response(JSON.stringify(body));
      }),
    );
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByText("Luis")).toBeInTheDocument();
    expect(screen.getByText("Clausura")).toBeInTheDocument();
  });
});
