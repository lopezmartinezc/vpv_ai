import { describe, it, expect } from "vitest";

import { feedSse, readSse } from "@/lib/sse";

describe("feedSse", () => {
  it("parses a complete frame", () => {
    const { frames, rest } = feedSse("", 'event: tool\ndata: {"name":"x"}\n\n');
    expect(frames).toEqual([{ event: "tool", data: '{"name":"x"}' }]);
    expect(rest).toBe("");
  });

  it("carries a partial frame across chunks", () => {
    // The network can cut anywhere — here, in the middle of the JSON.
    const a = feedSse("", 'event: done\ndata: {"reply":"ho');
    expect(a.frames).toEqual([]);
    const b = feedSse(a.rest, 'la"}\n\n');
    expect(b.frames).toEqual([{ event: "done", data: '{"reply":"hola"}' }]);
    expect(b.rest).toBe("");
  });

  it("handles several frames in one chunk", () => {
    const { frames } = feedSse(
      "",
      "event: tool\ndata: a\n\nevent: tool\ndata: b\n\nevent: done\ndata: c\n\n",
    );
    expect(frames.map((f) => f.event)).toEqual(["tool", "tool", "done"]);
  });

  it("defaults the event name to message", () => {
    const { frames } = feedSse("", "data: x\n\n");
    expect(frames[0].event).toBe("message");
  });
});

describe("readSse", () => {
  it("yields frames from a streamed body, including a final one without a blank line", async () => {
    const chunks = ['event: tool\ndata: {"n":1}\n\nevent: do', 'ne\ndata: {"ok":true}'];
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const c of chunks) controller.enqueue(new TextEncoder().encode(c));
        controller.close();
      },
    });
    const events: string[] = [];
    for await (const frame of readSse(new Response(body))) events.push(frame.event);
    expect(events).toEqual(["tool", "done"]);
  });
});
