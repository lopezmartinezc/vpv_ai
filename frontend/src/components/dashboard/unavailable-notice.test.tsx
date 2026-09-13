import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UnavailableNotice } from "./unavailable-notice";

describe("UnavailableNotice", () => {
  it("says nothing when every section loaded", () => {
    const { container } = render(<UnavailableNotice sections={[]} onRetry={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names the sections that could not load, in Spanish", () => {
    render(<UnavailableNotice sections={["standings", "copa"]} onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "No se pudo cargar la clasificación y la Copa.",
    );
  });

  it("retries", () => {
    const onRetry = vi.fn();
    render(<UnavailableNotice sections={["economy"]} onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("still names a section it has no label for", () => {
    render(<UnavailableNotice sections={["nueva"]} onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar nueva.");
  });
});
