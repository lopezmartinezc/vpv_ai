import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { copaLine, groupLine, LeagueSummary, weeklyLine } from "./league-summary";
import type {
  CopaFullResponse,
  CopaStandingEntry,
  EconomyResponse,
  GroupStandingsResponse,
} from "@/types";

const standing = (participant_id: number, rank: number, display_name: string) =>
  ({ participant_id, rank, display_name }) as CopaStandingEntry;

const copa: CopaFullResponse = {
  season_id: 1,
  season_name: "2026-27",
  standings: [standing(1, 1, "Rojo"), standing(2, 2, "Ana"), standing(3, 3, "Luis")],
  matchdays: [
    {
      matchday_number: 5,
      results: [
        { participant_id: 2, display_name: "Ana", goals_for: 3, goals_against: 1, goal_difference: 2, points: 3 },
        { participant_id: 3, display_name: "Luis", goals_for: 1, goals_against: 1, goal_difference: 0, points: 1 },
        { participant_id: 1, display_name: "Rojo", goals_for: 0, goals_against: 2, goal_difference: -2, points: 0 },
      ],
    },
  ],
};

const balance = (participant_id: number, weekly: number) => ({
  participant_id,
  display_name: `P${participant_id}`,
  initial_fee: 50,
  draft_fees: 10,
  weekly_total: weekly,
  net_balance: 60 + weekly,
});
const economy: EconomyResponse = {
  season_id: 1,
  balances: [balance(1, 12), balance(2, 7), balance(3, 12), balance(4, 0)],
};

const groups: GroupStandingsResponse = {
  season_id: 1,
  season_name: "Mundial",
  groups: [
    { rank: 1, group_name: "Los Pepes", total_points: 90, avg_points: 45, member_count: 2, members: [{ participant_id: 8, display_name: "X", total_points: 45 }] },
    { rank: 2, group_name: "Las Ranas", total_points: 80, avg_points: 40, member_count: 2, members: [{ participant_id: 2, display_name: "Ana", total_points: 40 }] },
  ],
};

describe("copaLine", () => {
  it("gives your place and your result in the matchday followed", () => {
    expect(copaLine(copa, 2, 5)).toEqual({ label: "Copa", value: "2.º de 3 · J5: V 3-1" });
    expect(copaLine(copa, 3, 5)?.value).toBe("3.º de 3 · J5: E 1-1");
    expect(copaLine(copa, 1, 5)?.value).toBe("1.º de 3 · J5: D 0-2");
  });

  it("leaves the result out for a matchday without one", () => {
    expect(copaLine(copa, 2, 6)?.value).toBe("2.º de 3");
  });

  it("names the leader to someone without a team", () => {
    expect(copaLine(copa, null, 5)).toEqual({ label: "Copa", value: "lidera Rojo" });
  });

  it("says nothing without a Copa", () => {
    expect(copaLine(null, 2, 5)).toBeNull();
  });
});

describe("weeklyLine", () => {
  it("gives what you have paid and your place, ties sharing it", () => {
    expect(weeklyLine(economy, 2)?.value).toBe("has pagado 7 € · 3.º que más ha pagado");
    expect(weeklyLine(economy, 3)?.value).toBe("has pagado 12 € · 1.º que más ha pagado");
  });

  it("says when you have paid nothing yet", () => {
    expect(weeklyLine(economy, 4)?.value).toBe("sin pagos todavía");
  });

  it("is yours only", () => {
    expect(weeklyLine(economy, null)).toBeNull();
    expect(weeklyLine(economy, 99)).toBeNull();
  });
});

describe("groupLine", () => {
  it("gives your group and its place", () => {
    expect(groupLine(groups, 2)).toEqual({ label: "Tu grupo", value: "Las Ranas · 2.º de 2" });
  });

  it("names the leading group to someone outside them", () => {
    expect(groupLine(groups, null)).toEqual({ label: "Grupos", value: "lidera Los Pepes" });
  });
});

describe("LeagueSummary", () => {
  const all = { seasonId: 12, participantId: 2, matchdayNumber: 5, copa, economy, groups };

  it("shows a line per part of a league, each linking to its page in this season", () => {
    render(<LeagueSummary {...all} economyEnabled />);
    expect(screen.getByRole("link", { name: /Copa/ })).toHaveAttribute("href", "/copa?season=12");
    expect(screen.getByRole("link", { name: /Semanales/ })).toHaveAttribute(
      "href",
      "/economia?season=12",
    );
    expect(screen.queryByRole("link", { name: /grupo/i })).not.toBeInTheDocument();
  });

  it("shows the groups and no Copa in a tournament", () => {
    render(<LeagueSummary {...all} isTournament />);
    expect(screen.getByRole("link", { name: /Tu grupo/ })).toHaveAttribute("href", "/grupos?season=12");
    expect(screen.queryByRole("link", { name: /Copa/ })).not.toBeInTheDocument();
  });

  it("leaves the payments out of a season without them", () => {
    render(<LeagueSummary {...all} economyEnabled={false} />);
    expect(screen.queryByRole("link", { name: /Semanales/ })).not.toBeInTheDocument();
  });

  it("draws nothing when there is nothing to sum up", () => {
    const { container } = render(
      <LeagueSummary seasonId={12} participantId={null} matchdayNumber={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
