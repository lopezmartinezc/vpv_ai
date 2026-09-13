import { describe, expect, it } from "vitest";
import { isMatchdayFinal, lineupDeadlineMs } from "@/lib/matchday-status";

const EARLY_MATCH = "2026-09-13T18:30:00Z";
const OVERRIDE = "2026-09-15T17:00:00Z";

describe("lineupDeadlineMs", () => {
  it("takes the server's deadline, even when an early match kicked off before it", () => {
    expect(lineupDeadlineMs({ deadline_at: OVERRIDE, first_match_at: EARLY_MATCH }, 30)).toBe(
      Date.parse(OVERRIDE),
    );
  });

  it("does not guess when the server says there is no deadline", () => {
    expect(lineupDeadlineMs({ deadline_at: null, first_match_at: EARLY_MATCH }, 30)).toBeNull();
  });

  it("falls back to kick-off minus the margin only for an API that does not send it", () => {
    expect(lineupDeadlineMs({ first_match_at: EARLY_MATCH }, 30)).toBe(
      Date.parse("2026-09-13T18:00:00Z"),
    );
    expect(lineupDeadlineMs({ first_match_at: null }, 30)).toBeNull();
  });
});

describe("isMatchdayFinal", () => {
  it("is final once finished with the stats in, or migrated as completed", () => {
    expect(isMatchdayFinal({ status: "finished", stats_ok: true })).toBe(true);
    expect(isMatchdayFinal({ status: "completed", stats_ok: false })).toBe(true);
    expect(isMatchdayFinal({ status: "finished", stats_ok: false })).toBe(false);
    expect(isMatchdayFinal({ status: "in_progress", stats_ok: true })).toBe(false);
  });
});
