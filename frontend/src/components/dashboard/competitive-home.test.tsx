import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompetitiveHome, isDeadlinePassed } from "./competitive-home";
import { apiClient } from "@/lib/api-client";
import type { MatchdayDetailResponse, MyLineupResponse } from "@/types";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiClient: { get: vi.fn() },
}));
vi.mock("./personal-playoff", () => ({
  PersonalPlayoff: ({
    participantId,
    matchdayNumber,
    phase,
  }: {
    participantId: number;
    matchdayNumber: number;
    phase: string;
  }) => (
    <p>
      Duelo de participante {participantId} · J{matchdayNumber} · {phase}
    </p>
  ),
}));
vi.mock("./matchday-incidents", () => ({
  MatchdayIncidents: ({ matchdayNumber }: { matchdayNumber: number }) => (
    <p>Incidencias J{matchdayNumber}</p>
  ),
}));

const FUTURE = "2099-01-01T20:00:00Z";
const PAST = "2020-01-01T20:00:00Z";

// J4 is the matchday whose lineup is being set. Its first kick-off is already
// past — an early match — but its effective deadline is not.
const current: MatchdayDetailResponse = {
  season_id: 1,
  number: 4,
  status: "in_progress",
  counts: true,
  stats_ok: false,
  first_match_at: PAST,
  deadline_at: FUTURE,
  matches: [],
  scores: [
    {
      rank: 1,
      participant_id: 42,
      display_name: "Azul",
      total_points: 40,
      formation: "4-3-3",
      pending_players: 2,
    },
    {
      rank: 2,
      participant_id: 43,
      display_name: "Rival",
      total_points: 35,
      formation: "4-3-3",
      pending_players: 4,
    },
  ],
};
const afterDeadline = { ...current, deadline_at: PAST };
const previous = { ...current, number: 3, status: "finished", stats_ok: true, deadline_at: PAST };
const inPlay = { ...previous, status: "in_progress", stats_ok: false };
const me: MyLineupResponse = {
  participant_id: 42,
  display_name: "Azul",
  lineup_deadline_min: 10,
  squad: [],
  current_lineup: null,
};
function mockMe(personal = me) {
  vi.mocked(apiClient.get).mockImplementation(async (path) => {
    if (path.endsWith("/me")) return personal as never;
    throw new Error("Unexpected request " + path);
  });
}
afterEach(() => vi.clearAllMocks());
const props = {
  seasonId: 1,
  current,
  previous,
  authenticated: true,
  standings: [],
  onRefresh: vi.fn(),
};
const heading = () => screen.getByRole("heading", { level: 1 });

describe("the matchday in play", () => {
  it("before the deadline follows the matchday being played, unclosed, and the lineup is the next one's", async () => {
    mockMe();
    render(<CompetitiveHome {...props} previous={inPlay} />);
    expect(await screen.findByRole("link", { name: "Preparar mi alineación" })).toHaveAttribute(
      "href",
      "/jornadas/4/alineacion?season=1",
    );
    expect(heading()).toHaveTextContent("Jornada 3");
    expect(screen.getByText("Mi alineación · J4")).toBeInTheDocument();
    expect(screen.getByText("Incidencias J3")).toBeInTheDocument();
    expect(screen.getByText(/Provisional/)).toBeInTheDocument();
    expect(screen.queryByText("Incidencias J4")).not.toBeInTheDocument();
  });

  it("goes by the effective deadline, not by an early first kick-off", async () => {
    mockMe();
    render(<CompetitiveHome {...props} />);
    await screen.findByRole("link", { name: "Preparar mi alineación" });
    expect(heading()).toHaveTextContent("Jornada 3");
  });

  it("after the deadline follows the new matchday: your points, you, the pending stats and the difference", async () => {
    mockMe();
    render(<CompetitiveHome {...props} current={afterDeadline} />);
    expect(await screen.findByText("Ver mi alineación")).toBeInTheDocument();
    expect(heading()).toHaveTextContent("Jornada 4");
    expect(screen.getByText("Incidencias J4")).toBeInTheDocument();
    expect(screen.getByText("Tú")).toBeInTheDocument();
    expect(screen.getByText("-5")).toBeInTheDocument();
    expect(screen.getByText("2 pendientes de puntuar")).toBeInTheDocument();
  });

  it("a visitor follows the same deadline, with no personal request", () => {
    const { rerender } = render(<CompetitiveHome {...props} authenticated={false} />);
    expect(heading()).toHaveTextContent("Jornada 3");
    rerender(<CompetitiveHome {...props} authenticated={false} current={afterDeadline} />);
    expect(heading()).toHaveTextContent("Jornada 4");
    expect(screen.getByText("Incidencias J4")).toBeInTheDocument();
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("with no previous matchday, says when the comparison will appear", () => {
    render(<CompetitiveHome {...props} authenticated={false} previous={null} />);
    expect(heading()).toHaveTextContent("Jornada 4");
    expect(screen.getByText(/aparecerá cuando cierre el plazo/)).toBeInTheDocument();
    expect(screen.queryByText("Incidencias J4")).not.toBeInTheDocument();
  });

  it("sums up the matchday being followed, never the hidden current points", async () => {
    mockMe();
    const prior = {
      ...previous,
      scores: [{ ...previous.scores[0], total_points: 12, pending_players: 0 }],
    };
    render(<CompetitiveHome {...props} previous={prior} />);
    await screen.findByRole("link", { name: "Preparar mi alineación" });
    const summary = screen.getByLabelText("Tu resumen competitivo");
    expect(summary).toHaveTextContent("Tus puntos · J3");
    expect(summary).toHaveTextContent("12");
    expect(summary).not.toHaveTextContent("40");
  });

  it("reads finished with confirmed stats as final", () => {
    render(
      <CompetitiveHome
        {...props}
        authenticated={false}
        current={{ ...current, status: "finished", stats_ok: true }}
      />,
    );
    expect(screen.getByText("Incidencias J4")).toBeInTheDocument();
    expect(screen.getByText(/Resultados finales/)).toBeInTheDocument();
  });

  it("reads a migrated, completed matchday as final", () => {
    render(
      <CompetitiveHome {...props} authenticated={false} current={{ ...current, status: "completed" }} />,
    );
    expect(screen.getByText("Incidencias J4")).toBeInTheDocument();
    expect(screen.getByText(/Resultados finales/)).toBeInTheDocument();
  });

  it("never takes a missing or unreadable deadline for a passed one; exact boundary", () => {
    const date = "2026-09-18T20:00:00Z",
      time = Date.parse(date);
    expect(isDeadlinePassed(null, time)).toBeNull();
    expect(isDeadlinePassed(undefined, time)).toBeNull();
    expect(isDeadlinePassed("invalid", time)).toBeNull();
    expect(isDeadlinePassed(date, time - 1)).toBe(false);
    expect(isDeadlinePassed(date, time)).toBe(true);
  });
});

describe("the playoff follows the matchday in play", () => {
  it("a duel still being played, before the next deadline", async () => {
    mockMe();
    render(<CompetitiveHome {...props} previous={inPlay} />);
    expect(await screen.findByText("Duelo de participante 42 · J3 · during")).toBeInTheDocument();
  });

  it("the next rival, once the previous matchday is closed", async () => {
    mockMe();
    render(<CompetitiveHome {...props} />);
    expect(await screen.findByText("Duelo de participante 42 · J4 · before")).toBeInTheDocument();
  });

  it("the new duel after the deadline, and its end once closed", async () => {
    mockMe();
    const { rerender } = render(<CompetitiveHome {...props} current={afterDeadline} />);
    expect(await screen.findByText("Duelo de participante 42 · J4 · during")).toBeInTheDocument();
    rerender(
      <CompetitiveHome {...props} current={{ ...afterDeadline, status: "finished", stats_ok: true }} />,
    );
    expect(screen.getByText("Duelo de participante 42 · J4 · final")).toBeInTheDocument();
  });
});

describe("your lineup", () => {
  it("does not invent a pending lineup when the personal request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("no participant"));
    render(<CompetitiveHome {...props} previous={null} />);
    expect(
      await screen.findByText("No se pudo consultar tu participación o alineación."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Sin alineación registrada")).not.toBeInTheDocument();
  });

  it("shows a confirmed lineup compactly", async () => {
    mockMe({
      ...me,
      current_lineup: {
        lineup_id: 1,
        formation: "4-3-3",
        confirmed: true,
        confirmed_at: null,
        telegram_sent: false,
        players: [],
      },
    });
    render(<CompetitiveHome {...props} />);
    expect(await screen.findByText("Alineación confirmada")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Preparar mi alineación" })).not.toBeInTheDocument();
  });

  it("asks a visitor to sign in", () => {
    render(<CompetitiveHome {...props} authenticated={false} />);
    expect(screen.getByRole("link", { name: "Iniciar sesión" })).toBeInTheDocument();
  });
});

describe("header and refresh", () => {
  it("names the matchday in one heading, with the season beside it", () => {
    render(
      <CompetitiveHome
        {...props}
        authenticated={false}
        current={afterDeadline}
        seasonName="Liga 2026-27"
      />,
    );
    expect(heading()).toHaveTextContent("Jornada 4");
    expect(screen.getByText("Liga 2026-27")).toBeInTheDocument();
  });

  it("refreshes by itself every minute, with no button for it", () => {
    vi.useFakeTimers();
    try {
      const onRefresh = vi.fn();
      render(<CompetitiveHome {...props} authenticated={false} onRefresh={onRefresh} />);
      expect(screen.queryByRole("button", { name: /Actualizar/ })).not.toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(59_000);
      });
      expect(onRefresh).not.toHaveBeenCalled();
      act(() => {
        vi.advanceTimersByTime(1_000);
      });
      expect(onRefresh).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("shortcuts", () => {
  it("keep the season in every link", () => {
    render(<CompetitiveHome {...props} authenticated={false} economyEnabled />);
    const expected: [RegExp, string][] = [
      [/Todas las jornadas/, "/jornadas?season=1"],
      [/Seguir la Copa/, "/copa?season=1"],
      [/Economía de la liga/, "/economia?season=1"],
      [/Rankings de la temporada/, "/ranking?season=1"],
    ];
    for (const [name, href] of expected) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
  });

  it("offer the Copa only in a league (IN-04)", () => {
    const { rerender } = render(<CompetitiveHome {...props} authenticated={false} isTournament />);
    expect(screen.queryByRole("link", { name: /Seguir la Copa/ })).not.toBeInTheDocument();
    rerender(<CompetitiveHome {...props} authenticated={false} />);
    expect(screen.getByRole("link", { name: /Seguir la Copa/ })).toBeInTheDocument();
  });

  it("offer the economy only in seasons that have it", () => {
    const { rerender } = render(
      <CompetitiveHome {...props} authenticated={false} economyEnabled={false} />,
    );
    expect(screen.queryByRole("link", { name: /Economía de la liga/ })).not.toBeInTheDocument();
    rerender(<CompetitiveHome {...props} authenticated={false} economyEnabled />);
    expect(screen.getByRole("link", { name: /Economía de la liga/ })).toBeInTheDocument();
  });
});
