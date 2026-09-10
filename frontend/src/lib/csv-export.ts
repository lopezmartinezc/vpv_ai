/**
 * CSV that Excel opens without an import wizard.
 *
 * A real .xlsx would need a dependency worth avoiding: `xlsx` (SheetJS) on the
 * npm registry has been unpublished since 2022 and carries known advisories,
 * and `exceljs` is about a megabyte. What CSV costs instead is locale
 * handling, and that is entirely solvable — a byte-order mark so Excel reads
 * UTF-8 and the accents survive, semicolons so Spanish Excel splits the
 * columns on a double click, and decimal commas so numbers arrive sortable
 * and filterable rather than as text.
 */

const SEPARATOR = ";";
/** Excel only reads a CSV as UTF-8 when it opens with a byte-order mark. */
const BOM = "\uFEFF";

export interface ExportColumn<T> {
  header: string;
  /** A number stays a number; strings are escaped. Nullish becomes an empty cell. */
  value: (row: T) => string | number | null | undefined;
}

/** One cell: numbers with a decimal comma, text escaped, nullish empty. */
export function formatCell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "";
    return String(value).replace(".", ",");
  }
  // A field holding the separator, a quote or a newline has to be quoted, and
  // inner quotes doubled — free-text notes will do all three sooner or later.
  if (/[";\r\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

export function toCsv<T>(rows: readonly T[], columns: readonly ExportColumn<T>[]): string {
  const header = columns.map((c) => formatCell(c.header)).join(SEPARATOR);
  const body = rows.map((row) => columns.map((c) => formatCell(c.value(row))).join(SEPARATOR));
  return BOM + [header, ...body].join("\r\n") + "\r\n";
}

/** `rendimiento-2026-2027-2026-09-10.csv` — a folder of these sorts by date. */
export function exportFilename(prefix: string, seasonName: string, today = new Date()): string {
  const slug = seasonName
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `${prefix}-${slug || "temporada"}-${today.toISOString().slice(0, 10)}.csv`;
}

/** Percentages the way the tables show them: 0.951 -> 95.1 */
export function asPercent(v: number | null | undefined): number | null {
  return v === null || v === undefined ? null : Math.round(v * 1000) / 10;
}

/** Hands the file to the browser. No-op where there is no DOM. */
export function downloadCsv(filename: string, csv: string): void {
  if (typeof document === "undefined") return;
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Freed on the next tick: revoking synchronously can cancel the download.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
