import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PersonalPlayoff } from "./personal-playoff";
import type { CompetitionSummary, MatchupEntry } from "@/types";

const apertura: CompetitionSummary = {
  id: 7,
  season_id: 1,
  name: "Apertura",
  type: "playoff",
  status: "regular",
};
const matchup: MatchupEntry = {
  id: 2,
  phase: "regular",
  group_label: null,
  round_label: null,
  round_number: 3,
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
const props = { seasonId: 1, matchdayNumber: 12, participantId: 10, phase: "during" as const };

/** The API: the season's competitions, and each one's matchups. */
function serve(
  matchups: Record<number, MatchupEntry[]> = { 7: [matchup] },
  competitions: CompetitionSummary[] = [apertura],
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const id = Number(input.match(/competitions\/(\d+)\/matchups/)?.[1]);
      const body = input.endsWith("/season/1")
        ? { season_id: 1, competitions }
        : { competition: competitions.find((c) => c.id === id), matchups: matchups[id] ?? [] };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
}
const loaded = (calls: number) => waitFor(() => expect(fetch).toHaveBeenCalledTimes(calls));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PersonalPlayoff, sized to the moment", () => {
  it("before the deadline shows only the rival, in one line", async () => {
    serve();
    render(<PersonalPlayoff {...props} phase="before" />);
    expect(await screen.findByText("Luis")).toBeInTheDocument();
    expect(screen.getByText(/tu rival:/)).toHaveTextContent("Apertura · Ronda 3 tu rival: Luis");
    expect(screen.queryByText("0 : —")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver DAVID Cup" })).toHaveAttribute(
      "href",
      "/playoffs?season=1",
    );
  });

  it("during the matchday shows a provisional score, what is pending, and — is not 0", async () => {
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
            pending_players: 4,
          },
        ]}
      />,
    );
    expect(await screen.findByText("0 : —")).toBeInTheDocument();
    expect(screen.getByText(/Provisional/)).toBeInTheDocument();
    expect(screen.getByText(/tú 4 · rival sin datos/)).toBeInTheDocument();
    expect(screen.queryByText(/99/)).not.toBeInTheDocument();
  });

  it("turns the scoreboard around for side B", async () => {
    serve({ 7: [{ ...matchup, score_b: 21 }] });
    render(<PersonalPlayoff {...props} participantId={20} />);
    expect(await screen.findByText("21 : 0")).toBeInTheDocument();
    expect(screen.getByText("Ana")).toBeInTheDocument();
  });

  it("when the matchday is closed, says how the duel ended", async () => {
    const cases: [Partial<MatchupEntry>, string][] = [
      [{ score_a: 30, score_b: 20, winner_participant_id: 10 }, "Duelo ganado"],
      [{ score_a: 20, score_b: 30, winner_participant_id: 20 }, "Duelo perdido"],
      [{ score_a: 25, score_b: 25, winner_participant_id: null }, "Empate"],
    ];
    for (const [result, text] of cases) {
      serve({ 7: [{ ...matchup, ...result }] });
      const { unmount } = render(<PersonalPlayoff {...props} phase="final" />);
      expect(await screen.findByText(text)).toBeInTheDocument();
      expect(screen.getByText(/· Final/)).toBeInTheDocument();
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it("does not call a result before the matchday is closed", async () => {
    serve({ 7: [{ ...matchup, score_a: 30, score_b: 20, winner_participant_id: 10 }] });
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByText("30 : 20")).toBeInTheDocument();
    expect(screen.queryByText("Duelo ganado")).not.toBeInTheDocument();
  });
});

describe("PersonalPlayoff draws nothing when there is nothing to show", () => {
  it("while loading", () => {
    serve();
    const { container } = render(<PersonalPlayoff {...props} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("when the season has no playoff", async () => {
    serve({}, []);
    const { container } = render(<PersonalPlayoff {...props} />);
    await loaded(1);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("when you have no duel this matchday, and it does not assume a bye", async () => {
    serve();
    const { container } = render(<PersonalPlayoff {...props} matchdayNumber={13} />);
    await loaded(2);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(screen.queryByText(/descanso/i)).not.toBeInTheDocument();
  });

  it("without a participant, and asks for nothing", () => {
    serve();
    const { container } = render(<PersonalPlayoff {...props} participantId={null} />);
    expect(fetch).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it("for the playoff without your duel, showing only the one with it", async () => {
    const clausura = { ...apertura, id: 8, name: "Clausura" };
    serve({ 7: [], 8: [{ ...matchup, id: 3 }] }, [apertura, clausura]);
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByText(/Clausura/)).toBeInTheDocument();
    expect(screen.queryByText(/Apertura/)).not.toBeInTheDocument();
  });
});

describe("PersonalPlayoff, other cases", () => {
  it("tells a rival still to be decided from none at all", async () => {
    serve({ 7: [{ ...matchup, participant_b_id: null, participant_b_name: null, feeder_b_id: 9 }] });
    const { unmount } = render(<PersonalPlayoff {...props} phase="before" />);
    expect(await screen.findByText(/rival por decidir/)).toBeInTheDocument();
    unmount();
    serve({ 7: [{ ...matchup, participant_b_id: null, participant_b_name: null }] });
    render(<PersonalPlayoff {...props} phase="before" />);
    expect(await screen.findByText(/sin rival asignado/)).toBeInTheDocument();
  });

  it("refuses a duel that belongs to another season", async () => {
    serve({ 7: [matchup] }, [apertura]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) =>
        input.endsWith("/season/1")
          ? new Response(JSON.stringify({ season_id: 1, competitions: [apertura] }))
          : new Response(
              JSON.stringify({ competition: { ...apertura, season_id: 2 }, matchups: [matchup] }),
            ),
      ),
    );
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo cargar tu duelo de DAVID Cup");
    expect(screen.queryByText("Luis")).not.toBeInTheDocument();
  });

  it("says when it could not load, and retries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 500 })),
    );
    render(<PersonalPlayoff {...props} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo cargar tu duelo de DAVID Cup");
    serve();
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("0 : —")).toBeInTheDocument();
  });

  it("reloads on refreshKey without remounting", async () => {
    serve({ 7: [{ ...matchup, score_b: 1 }] });
    const { rerender } = render(<PersonalPlayoff {...props} refreshKey={0} />);
    expect(await screen.findByText("0 : 1")).toBeInTheDocument();
    serve({ 7: [{ ...matchup, score_b: 7 }] });
    rerender(<PersonalPlayoff {...props} refreshKey={1} />);
    expect(await screen.findByText("0 : 7")).toBeInTheDocument();
  });

  it("drops the old season's duel as soon as the season changes", async () => {
    serve();
    const { rerender } = render(<PersonalPlayoff {...props} />);
    await screen.findByText("Luis");
    rerender(<PersonalPlayoff {...props} seasonId={2} />);
    expect(screen.queryByText("Luis")).not.toBeInTheDocument();
  });
});
