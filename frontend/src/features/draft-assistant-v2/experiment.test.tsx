import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import { DraftChatExperiment } from "./experiment";

vi.mock("@/components/draft/assistant-panel", () => ({
  AssistantPanel: (): ReactElement => <input aria-label="Legacy question" />,
}));
vi.mock("./panel", () => ({
  ExperimentalPanel: ({ active }: { active: boolean }): ReactElement =>
    <div data-testid="v2" data-active={String(active)}>V2 only</div>,
}));

describe("DraftChatExperiment", () => {
  it("defaults to legacy without mounting V2 and preserves legacy state across switches", () => {
    render(<DraftChatExperiment draftId={1} seasonId={1} phase="preseason"
      liveToken="1" context={{selected_player_ids: [], participant_id: null,
        position: null, team: "", search: "", order: "priority"}}
      participants={[]} players={[]} onSelect={vi.fn()} />);
    expect(screen.queryByTestId("v2")).toBeNull();
    fireEvent.change(screen.getByLabelText("Legacy question"), {target: {value: "Keep this"}});
    fireEvent.click(screen.getByRole("button", {name: "Experimental V2"}));
    expect(screen.getByTestId("v2")).toHaveAttribute("data-active", "true");
    expect(screen.getByLabelText("Legacy question")).toHaveValue("Keep this");
    fireEvent.click(screen.getByRole("button", {name: "Actual"}));
    expect(screen.getByTestId("v2")).toHaveAttribute("data-active", "false");
    expect(screen.getByLabelText("Legacy question")).toBeVisible();
  });
});
