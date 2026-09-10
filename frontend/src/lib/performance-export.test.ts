/**
 * The performance export must carry what the tables compute on the fly, not
 * just the raw fields: a spreadsheet of appearances without the starts share,
 * or of CV without the consistency the column actually shows, loses the part
 * people were reading.
 */

import { describe, expect, it } from "vitest";

import type { AdvancedPlayerStat, PlayerStatRow } from "@/types";
import {
  ADVANCED_COLUMNS,
  PLAYER_COLUMNS,
  advancedToCsv,
  performanceFilename,
  playersToCsv,
} from "./performance-export";

const base: PlayerStatRow = {
  player_id: 1,
  display_name: "Pedri González",
  photo_path: null,
  position: "MED",
  team_name: "Barcelona",
  goals: 5,
  penalty_goals: 1,
  own_goals: 0,
  assists: 9,
  penalties_saved: 0,
  yellow_cards: 3,
  red_cards: 0,
  avg_marca: 6.8,
  avg_as: 6.5,
  minutes_played: 2400,
  matchdays_played: 30,
  started_count: 24,
  avg_points: 8.1,
  total_points: 243,
};

const advanced: AdvancedPlayerStat = {
  player_id: 1,
  display_name: "Pedri González",
  photo_path: null,
  position: "MED",
  team_name: "Barcelona",
  matchdays_played: 30,
  minutes_played: 2400,
  total_points: 243,
  avg_points: 8.1,
  std_dev: 3.2,
  cv: 0.4,
  p10: 3,
  p50: 8,
  p90: 14,
  pp90: 9.1,
  ci_lower: 6.9,
  ci_upper: 9.3,
  form_5: 8.8,
  trend: "rising",
};

const cells = (csv: string, row: number): string[] =>
  csv.replace(/^﻿/, "").split("\r\n")[row].split(";");

const at = (columns: { header: string }[], header: string): number =>
  columns.findIndex((c) => c.header === header);

describe("playersToCsv", () => {
  it("keeps the accents readable in Excel", () => {
    expect(playersToCsv([base])).toContain("Pedri González");
  });

  it("carries the starts share the table derives, not just the raw count", () => {
    const csv = playersToCsv([base]);
    expect(cells(csv, 1)[at(PLAYER_COLUMNS, "Titularidades")]).toBe("24");
    expect(cells(csv, 1)[at(PLAYER_COLUMNS, "Titular %")]).toBe("80");
  });

  it("writes minutes per match, which separates a starter from a substitute", () => {
    expect(cells(playersToCsv([base]), 1)[at(PLAYER_COLUMNS, "Minutos por partido")]).toBe("80");
  });

  it("does not divide by zero for a player who never appeared", () => {
    const unused = { ...base, matchdays_played: 0, started_count: 0, minutes_played: 0 };
    const row = cells(playersToCsv([unused]), 1);
    expect(row[at(PLAYER_COLUMNS, "Titular %")]).toBe("");
    expect(row[at(PLAYER_COLUMNS, "Minutos por partido")]).toBe("");
  });

  it("writes decimals with a comma so Excel reads them as numbers", () => {
    expect(cells(playersToCsv([base]), 1)[at(PLAYER_COLUMNS, "Media pts")]).toBe("8,1");
  });

  it("leaves an empty cell where a mark is missing", () => {
    const csv = playersToCsv([{ ...base, avg_marca: null }]);
    expect(cells(csv, 1)[at(PLAYER_COLUMNS, "Nota Marca")]).toBe("");
  });

  it("has one cell per column on every row", () => {
    const csv = playersToCsv([base, { ...base, player_id: 2 }]);
    for (const row of [0, 1, 2]) expect(cells(csv, row)).toHaveLength(PLAYER_COLUMNS.length);
  });
});

describe("advancedToCsv", () => {
  it("exports consistency the way the column reads it, not just CV", () => {
    const csv = advancedToCsv([advanced]);
    expect(cells(csv, 1)[at(ADVANCED_COLUMNS, "Coef. variacion")]).toBe("0,4");
    expect(cells(csv, 1)[at(ADVANCED_COLUMNS, "Consistencia %")]).toBe("60");
  });

  it("carries floor, median and ceiling under names you can read a year later", () => {
    const csv = advancedToCsv([advanced]);
    expect(cells(csv, 1)[at(ADVANCED_COLUMNS, "Suelo (P10)")]).toBe("3");
    expect(cells(csv, 1)[at(ADVANCED_COLUMNS, "Techo (P90)")]).toBe("14");
  });

  it("keeps the confidence interval and the trend", () => {
    const csv = advancedToCsv([advanced]);
    expect(cells(csv, 1)[at(ADVANCED_COLUMNS, "IC95 inferior")]).toBe("6,9");
    expect(cells(csv, 1)[at(ADVANCED_COLUMNS, "Tendencia")]).toBe("rising");
  });

  it("leaves form empty for a player with too few matches to have one", () => {
    const csv = advancedToCsv([{ ...advanced, form_5: null }]);
    expect(cells(csv, 1)[at(ADVANCED_COLUMNS, "Forma (ultimos 5)")]).toBe("");
  });

  it("exports an empty table as headers alone", () => {
    expect(advancedToCsv([]).trimEnd().split("\r\n")).toHaveLength(1);
  });
});

describe("headers", () => {
  it("are unique in both tables — Excel would silently rename duplicates", () => {
    for (const columns of [PLAYER_COLUMNS, ADVANCED_COLUMNS]) {
      const headers = columns.map((c) => c.header);
      expect(new Set(headers).size).toBe(headers.length);
    }
  });
});

describe("performanceFilename", () => {
  it("says which lens it came from", () => {
    const day = new Date("2026-09-10T20:00:00Z");
    expect(performanceFilename("rendimiento", "2026-2027", day)).toBe(
      "rendimiento-2026-2027-2026-09-10.csv",
    );
    expect(performanceFilename("avanzado", "2026-2027", day)).toBe(
      "avanzado-2026-2027-2026-09-10.csv",
    );
  });
});
