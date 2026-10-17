import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DeadlineBanner, deadlineState } from "./deadline-banner";

const NOW = Date.parse("2026-10-17T12:00:00Z");

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("deadlineState", () => {
  it.each([null, "", "invalid"])("has nothing to say without a deadline (%s)", (value) => {
    expect(deadlineState(value, NOW)).toBeNull();
  });
  it.each(["2026-10-17T12:00:00Z", "2026-10-17T11:59:59Z"])("closes at or after %s", (value) => {
    expect(deadlineState(value, NOW)).toEqual({ label: "Plazo cerrado", tone: "closed" });
  });
  it("keeps the last partial minute open and formats hours", () => {
    expect(deadlineState("2026-10-17T12:00:01Z", NOW)?.label).toBe("Cierre en 1 minuto");
    expect(deadlineState("2026-10-17T13:02:00Z", NOW)?.label).toBe("Cierre en 1h 2m");
    expect(deadlineState("2026-10-17T12:02:00Z", NOW)?.label).toBe("Cierre en 2 minutos");
  });
  it("turns urgent in the last 30 minutes", () => {
    expect(deadlineState("2026-10-17T12:30:00Z", NOW)?.tone).toBe("urgent");
    expect(deadlineState("2026-10-17T12:30:01Z", NOW)?.tone).toBe("open");
  });
});

describe("DeadlineBanner", () => {
  it("uses the API timestamp, updates through closing and cleans up", () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const view = render(<DeadlineBanner deadlineAt="2026-10-17T14:00:01+02:00" />);
    expect(screen.getByRole("status")).toHaveTextContent("Cierre en 1 minuto");
    expect(screen.getByRole("status").className).toContain("vpv-danger");
    act(() => vi.advanceTimersByTime(15_000));
    expect(screen.getByRole("status")).toHaveTextContent("Plazo cerrado");
    view.rerender(<DeadlineBanner deadlineAt={null} />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    view.rerender(<DeadlineBanner deadlineAt="2026-10-17T13:00:00Z" />);
    expect(screen.getByRole("status")).toHaveTextContent("Cierre en 1h 0m");
    expect(screen.getByRole("status").className).toContain("amber");
    view.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
