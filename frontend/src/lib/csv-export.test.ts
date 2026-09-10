/**
 * The CSV engine shared by every export: what Excel needs in order to open a
 * file on a double click and treat its numbers as numbers.
 */

import { describe, expect, it } from "vitest";

import { asPercent, exportFilename, formatCell, toCsv } from "./csv-export";

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
  const rows = [{ name: "Pedri", pts: 8.1 }, { name: "Xavi", pts: null }];
  const columns = [
    { header: "Jugador", value: (r: (typeof rows)[number]) => r.name },
    { header: "Pts", value: (r: (typeof rows)[number]) => r.pts },
  ];

  it("opens with a BOM so Excel keeps the accents", () => {
    expect(toCsv(rows, columns).startsWith("\uFEFF")).toBe(true);
  });

  it("writes one header row and one row per record", () => {
    expect(toCsv(rows, columns).trimEnd().split("\r\n")).toHaveLength(3);
  });

  it("exports an empty set as headers alone", () => {
    expect(toCsv([], columns).trimEnd().split("\r\n")).toHaveLength(1);
  });
});

describe("asPercent", () => {
  it("shows a rate the way the tables do, to one decimal", () => {
    expect(asPercent(0.9512)).toBe(95.1);
    expect(asPercent(null)).toBeNull();
  });
});

describe("exportFilename", () => {
  it("names the file by prefix, season and date so a folder sorts by date", () => {
    expect(exportFilename("rendimiento", "2026-2027", new Date("2026-09-10T20:00:00Z")))
      .toBe("rendimiento-2026-2027-2026-09-10.csv");
  });

  it("keeps a season with spaces or accents filesystem-safe", () => {
    expect(exportFilename("draft", "Mundial 2026", new Date("2026-09-10T20:00:00Z")))
      .toBe("draft-mundial-2026-2026-09-10.csv");
  });
});
