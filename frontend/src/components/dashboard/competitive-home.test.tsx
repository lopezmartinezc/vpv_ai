import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompetitiveHome, isDeadlinePassed } from "./competitive-home";
import { apiClient } from "@/lib/api-client";
import type { MatchdayDetailResponse, MyLineupResponse } from "@/types";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiClient: { get: vi.fn() },
}));
vi.mock("./personal-playoff", () => ({
  PersonalPlayoff: ({ participantId }: { participantId: number }) => (
    <p>Duelo de participante {participantId}</p>
  ),
}));
vi.mock("./matchday-incidents", () => ({
  MatchdayIncidents: ({ matchdayNumber }: { matchdayNumber: number }) => (
    <p>Incidencias J{matchdayNumber}</p>
  ),
}));

const current: MatchdayDetailResponse = {
  season_id: 1,
  number: 4,
  status: "in_progress",
  counts: true,
  stats_ok: false,
  first_match_at: "2020-01-01T20:00:00Z",
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
const previous = { ...current, number: 3, status: "finished", stats_ok: true };
const me: MyLineupResponse = {
  participant_id: 42,
  display_name: "Azul",
  lineup_deadline_min: 10,
  squad: [],
  current_lineup: null,
};
const status = (date: string | null, number = 4) => ({
  has_lineup: false,
  matchday_number: number,
  deadline_at: date,
  minutes_remaining: 0,
});
function mockApi(deadline: ReturnType<typeof status>, personal = me) {
  vi.mocked(apiClient.get).mockImplementation(async (path) => {
    if (path.endsWith("/me")) return personal as never;
    if (path.endsWith("/deadline-status")) return deadline as never;
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

describe("competitive home", () => {
  it("uses the effective deadline, not first_match_at: before it, shows J3 and prepares J4", async () => {
    mockApi(status("2099-01-01T20:00:00Z"));
    render(<CompetitiveHome {...props} />);
    expect(await screen.findByRole("link", { name: "Preparar mi alineación" })).toHaveAttribute(
      "href",
      "/jornadas/4/alineacion?season=1",
    );
    expect(screen.getByText("Incidencias J3")).toBeInTheDocument();
    expect(screen.queryByText("Incidencias J4")).not.toBeInTheDocument();
    expect(screen.getByText("Duelo de participante 42")).toBeInTheDocument();
  });

  it("after the deadline shows your points, you, the pending stats and the difference", async () => {
    mockApi(status("2020-01-01T20:00:00Z"));
    render(<CompetitiveHome {...props} />);
    expect(await screen.findByText("Incidencias J4")).toBeInTheDocument();
    expect(screen.getByText("Tú")).toBeInTheDocument();
    expect(screen.getByText("-5")).toBeInTheDocument();
    expect(screen.getByText("2 pendientes de puntuar")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver mi alineación" })).toBeInTheDocument();
  });

  it("does not invent a pending lineup when the personal request fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("no participant"));
    render(<CompetitiveHome {...props} previous={null} />);
    expect(
      await screen.findByText("No se pudo consultar tu participación o alineación."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Sin alineación registrada")).not.toBeInTheDocument();
    expect(screen.queryByText("Incidencias J4")).not.toBeInTheDocument();
  });

  it("shows a confirmed lineup compactly, and refreshes without any save action", async () => {
    mockApi(status("2099-01-01T20:00:00Z"), {
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
    fireEvent.click(screen.getByRole("button", { name: "Actualizar jornada" }));
    await waitFor(() => expect(props.onRefresh).toHaveBeenCalled());
  });

  it("asks a visitor for no private endpoint and shows no current rival", () => {
    render(<CompetitiveHome {...props} authenticated={false} previous={null} />);
    expect(apiClient.get).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(screen.queryByText("Incidencias J4")).not.toBeInTheDocument();
  });

  it("reads finished with confirmed stats as final, for visitors too", () => {
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

  it("never takes null or another matchday for a passed deadline; exact boundary", () => {
    const date = "2026-09-18T20:00:00Z",
      time = Date.parse(date);
    expect(isDeadlinePassed(status(null), 4, time)).toBeNull();
    expect(isDeadlinePassed(status("invalid"), 4, time)).toBeNull();
    expect(isDeadlinePassed(status(date, 3), 4, time)).toBeNull();
    expect(isDeadlinePassed(status(date), 4, time - 1)).toBe(false);
    expect(isDeadlinePassed(status(date), 4, time)).toBe(true);
  });

  it("before the deadline sums up the previous matchday, never the hidden current points", async () => {
    mockApi(status("2099-01-01T20:00:00Z"));
    const prior = {
      ...previous,
      scores: [{ ...previous.scores[0], total_points: 12, pending_players: 0 }],
    };
    render(<CompetitiveHome {...props} previous={prior} seasonName="Liga de prueba" />);
    await screen.findByRole("link", { name: "Preparar mi alineación" });
    const summary = screen.getByLabelText("Tu resumen competitivo");
    expect(summary).toHaveTextContent("Tus puntos · J3");
    expect(summary).toHaveTextContent("12");
    expect(summary).not.toHaveTextContent("40");
  });

  it("before the deadline compares nothing when the previous matchday is not closed either", async () => {
    mockApi(status("2099-01-01T20:00:00Z"));
    render(
      <CompetitiveHome {...props} previous={{ ...previous, status: "in_progress", stats_ok: false }} />,
    );
    expect(await screen.findByText(/aparecerá cuando se verifique el cierre/)).toBeInTheDocument();
    expect(screen.queryByText("Incidencias J3")).not.toBeInTheDocument();
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
