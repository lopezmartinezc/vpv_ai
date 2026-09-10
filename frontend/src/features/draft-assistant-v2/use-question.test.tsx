import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { askV2 } from "./api";
import type { Ask } from "./contracts";
import { useQuestion } from "./use-question";

vi.mock("./api", () => ({askV2: vi.fn()}));
const request: Ask = {question: "Evalúa", provider: "openai", model: "test",
  mode: "quick", participation: "mixto", context: {selected_player_ids: [],
    participant_id: null, position: null, team: "", search: "", order: "priority"}};

describe("useQuestion", () => {
  it("blocks duplicates and aborts the pending V2 call when switching to legacy", async () => {
    let signal: AbortSignal | undefined;
    vi.mocked(askV2).mockImplementation((_id, _request, current) => {
      signal = current;
      return new Promise((_resolve, reject) => {
        current.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });
    const onAnswer = vi.fn();
    const {result, rerender} = renderHook(({active}) => useQuestion(1, active, onAnswer),
      {initialProps: {active: true}});
    act(() => {void result.current.send(request); void result.current.send(request);});
    expect(askV2).toHaveBeenCalledTimes(1);
    rerender({active: false});
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(signal?.aborted).toBe(true);
    expect(onAnswer).not.toHaveBeenCalled();
    expect(result.current.error).toContain("cancelada");
  });
});
