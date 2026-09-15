import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlayoffsCard } from "./playoffs-card";
import { apiClient } from "@/lib/api-client";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

const get = vi.mocked(apiClient.get);
// The card chains three loads and two effects before it settles; under a full
// parallel run that took longer than the default second.
const SLOW = { timeout: 5000 };

afterEach(() => get.mockReset());

function serve(playoffName: string) {
  get.mockImplementation(async (path: string) => {
    if (path.startsWith("/competitions/formats")) {
      return [
        {
          format_id: "liga_berger_ko8_bo3",
          display_name: "Liga todos contra todos + KO top-8, final al mejor de 3",
          n_rounds_regular: 11,
          n_rounds_ko: 5,
        },
      ];
    }
    return {
      season_id: 12,
      competitions: [{ id: 7, season_id: 12, name: playoffName, type: "playoff", status: "pending" }],
    };
  });
}

describe("PlayoffsCard for the Liga", () => {
  it("counts the season's own participants when listing formats", async () => {
    serve("Apertura");
    render(
      <PlayoffsCard
        seasonId={12}
        matchdayStart={6}
        matchdayEnd={38}
        playoffName="Apertura"
        defaultFormatId="liga_berger_ko8_bo3"
      />,
    );
    await waitFor(
      () => expect(get).toHaveBeenCalledWith("/competitions/formats?season_id=12"),
      SLOW,
    );
    expect(await screen.findByText(/Fase regular: J6 – J16/, {}, SLOW)).toBeInTheDocument();
    expect(await screen.findByDisplayValue("17,18,19,20,21", {}, SLOW)).toBeInTheDocument();
  });

  it("suggests the Clausura right after the Apertura: league J22-J32, KO J33-J37", async () => {
    serve("Clausura");
    render(
      <PlayoffsCard
        seasonId={12}
        matchdayStart={6}
        matchdayEnd={38}
        playoffName="Clausura"
        defaultFormatId="liga_berger_ko8_bo3"
        order={1}
      />,
    );
    expect(await screen.findByDisplayValue("22", {}, SLOW)).toBeInTheDocument();
    expect(await screen.findByText(/Fase regular: J22 – J32/, {}, SLOW)).toBeInTheDocument();
    expect(await screen.findByDisplayValue("33,34,35,36,37", {}, SLOW)).toBeInTheDocument();
  });
});
