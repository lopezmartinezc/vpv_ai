/**
 * The export exists so the board can be worked on in Excel, which means the
 * numbers have to arrive as numbers and every column has to travel — including
 * the ones the table hides and the ones it has no room for.
 */

import { describe, expect, it } from "vitest";

import type { DraftValuePlayer } from "@/types";
import { EXPORT_COLUMNS, exportFilename, formatCell, toCsv } from "./draft-export";

const player = (over: Partial<DraftValuePlayer> = {}): DraftValuePlayer =>
  ({
    player_id: 1,
    display_name: "Pedri González",
    team_name: "Barcelona",
    position: "MED",
    photo_path: null,
    games_played: 30,
    seasons_played: 4,
    avg_points: 8.1,
    total_points: 243,
    ensemble_score: 7.9,
    simple_avg: 7.4,
    second_half_score: 8.2,
    productivity_score: 6.1,
    stability_score: 7.7,
    trend_score: null,
    career_trend_pct: 0.125,
    marca_avg: 6.8,
    as_avg: 6.5,
    availability: 0.95,
    consistency: 0.82,
    second_half_avg: null,
    goals: 5,
    assists: 9,
    signal: "hold",
    signal_reasons: [],
    priority: 448.2,
    priority_base: 440,
    vorp: 20.5,
    participation: 0.9,
    ...over,
  }) as DraftValuePlayer;

const cellsOf = (csv: string, row: number): string[] =>
  csv.replace(/^﻿/, "").split("\r\n")[row].split(";");

const columnIndex = (header: string): number =>
  EXPORT_COLUMNS.findIndex((c) => c.header === header);

describe("formatCell", () => {
  it("writes decimals with a comma, which is what Spanish Excel reads as a number", () => {
    expect(formatCell(448.2)).toBe("448,2");
    expect(formatCell(30)).toBe("30");
  });

  it("quotes a field containing the separator, and doubles inner quotes", () => {
    expect(formatCell("Duda; mirar prensa")).toBe('"Duda; mirar prensa"');
    expect(formatCell('Dijo "titular"')).toBe('"Dijo ""titular"""');
  });

  it("quotes a field with a newline so it stays one cell", () => {
    expect(formatCell("linea 1\nlinea 2")).toBe('"linea 1\nlinea 2"');
  });

  it("leaves an empty cell for nothing, rather than the word null", () => {
    expect(formatCell(null)).toBe("");
    expect(formatCell(undefined)).toBe("");
  });

  it("does not write Infinity or NaN into a spreadsheet", () => {
    expect(formatCell(Number.POSITIVE_INFINITY)).toBe("");
    expect(formatCell(Number.NaN)).toBe("");
  });
});

describe("toCsv", () => {
  it("opens with a BOM so Excel keeps the accents", () => {
    expect(toCsv([player()]).startsWith("﻿")).toBe(true);
    expect(toCsv([player()])).toContain("Pedri González");
  });

  it("writes one header row and one row per player", () => {
    const csv = toCsv([player(), player({ player_id: 2 })]);
    const lines = csv.trimEnd().split("\r\n");
    expect(lines).toHaveLength(3);
    expect(cellsOf(csv, 0)).toHaveLength(EXPORT_COLUMNS.length);
    expect(cellsOf(csv, 1)).toHaveLength(EXPORT_COLUMNS.length);
  });

  it("carries the model scores the table keeps hidden behind '+ Columnas'", () => {
    const csv = toCsv([player()]);
    for (const header of ["Ensemble", "Media simple", "Estabilidad", "Productividad"]) {
      expect(cellsOf(csv, 0)).toContain(header);
    }
    expect(cellsOf(csv, 1)[columnIndex("Ensemble")]).toBe("7,9");
  });

  it("carries fields the table has no room for at all", () => {
    const csv = toCsv([player({ goals: 5, assists: 9, marca_avg: 6.8 })]);
    expect(cellsOf(csv, 1)[columnIndex("Goles")]).toBe("5");
    expect(cellsOf(csv, 1)[columnIndex("Asistencias")]).toBe("9");
    expect(cellsOf(csv, 1)[columnIndex("Nota Marca")]).toBe("6,8");
  });

  it("turns rates into percentages, which is how the table shows them", () => {
    const csv = toCsv([player({ availability: 0.95, participation: 0.9 })]);
    expect(cellsOf(csv, 1)[columnIndex("Disponibilidad %")]).toBe("95");
    expect(cellsOf(csv, 1)[columnIndex("Participacion %")]).toBe("90");
  });

  it("exports confidence with the reason behind it, not just the score", () => {
    const csv = toCsv([player({ seasons_played: 0, is_new: true })]);
    expect(cellsOf(csv, 1)[columnIndex("Motivo confianza")]).toMatch(/hist[óo]rico/i);
  });

  it("keeps a note with a semicolon in one cell", () => {
    const csv = toCsv([player({ note: "Ojo; vuelve de lesion" })]);
    expect(cellsOf(csv, 0)).toHaveLength(EXPORT_COLUMNS.length);
    expect(csv).toContain('"Ojo; vuelve de lesion"');
  });

  it("writes readable tag labels, not the raw keys", () => {
    const csv = toCsv([player({ tags: ["titular"] })]);
    expect(cellsOf(csv, 1)[columnIndex("Tags")].toLowerCase()).toContain("titular");
  });

  it("survives a player with almost nothing filled in", () => {
    const bare = { player_id: 9, display_name: "Nuevo", team_name: "X", position: "DEF" };
    const csv = toCsv([bare as DraftValuePlayer]);
    expect(cellsOf(csv, 1)).toHaveLength(EXPORT_COLUMNS.length);
    expect(cellsOf(csv, 1)[columnIndex("Jugador")]).toBe("Nuevo");
  });

  it("exports an empty board as headers alone", () => {
    expect(toCsv([]).trimEnd().split("\r\n")).toHaveLength(1);
  });

  it("has no duplicate headers — Excel would silently rename them", () => {
    const headers = EXPORT_COLUMNS.map((c) => c.header);
    expect(new Set(headers).size).toBe(headers.length);
  });
});

describe("exportFilename", () => {
  it("names the file by season and date so a folder sorts chronologically", () => {
    expect(exportFilename("2026-2027", new Date("2026-09-10T20:00:00Z"))).toBe(
      "draft-2026-2027-2026-09-10.csv",
    );
  });

  it("keeps a season with spaces or accents filesystem-safe", () => {
    expect(exportFilename("Mundial 2026", new Date("2026-09-10T20:00:00Z"))).toBe(
      "draft-mundial-2026-2026-09-10.csv",
    );
  });
});
