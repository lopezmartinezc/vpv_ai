import { afterEach, describe, expect, it, vi } from "vitest";
import { askV2, fetchV2 } from "./api";
import type { Ask } from "./contracts";

const request: Ask = {question: "Evalúa", provider: "openai", model: "test",
  mode: "quick", participation: "mixto", context: {selected_player_ids: [],
    participant_id: null, position: null, team: "", search: "", order: "priority"}};

afterEach(() => {vi.unstubAllGlobals(); localStorage.clear();});

describe("V2 transport", () => {
  it("sends authentication exclusively to V2", async () => {
    localStorage.setItem("vpv_token", "test-token");
    const fetch = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    await fetchV2("/1/history");
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/draft-assistant-v2/1/history"),
      expect.objectContaining({headers: expect.objectContaining({Authorization: "Bearer test-token"})}));
  });
  it("reports server errors without accepting malformed responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"message":"Busy"}', {status: 409})));
    await expect(fetchV2("/1/history")).rejects.toThrow("Busy");
  });
  it("rejects invalid outgoing context before a network request", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    await expect(askV2(1, {...request, question: ""}, new AbortController().signal, vi.fn())).rejects.toThrow();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("propagates SSE errors and rejects missing final answers", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('event: error\ndata: {"message":"Timeout"}\n\n')));
    await expect(askV2(1, request, new AbortController().signal, vi.fn())).rejects.toThrow("Timeout");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("")));
    await expect(askV2(1, request, new AbortController().signal, vi.fn())).rejects.toThrow("sin respuesta");
  });
});
