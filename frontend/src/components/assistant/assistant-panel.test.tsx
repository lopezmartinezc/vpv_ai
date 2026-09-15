import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AssistantPanel } from "./assistant-panel";
import { AssistantPanel as DraftAssistantPanel } from "@/components/draft/assistant-panel";
import { apiClient } from "@/lib/api-client";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiClient: { get: vi.fn() },
}));

const DONE = {
  reply: "Raphinha juega: FF 80 %.",
  provider: "anthropic",
  model: "claude-opus-5",
  tool_calls: [{ name: "mi_plantilla", arguments: {} }],
  truncated: false,
};

function streamed(): Response {
  return new Response(
    'event: tool\ndata: {"name": "mi_plantilla", "arguments": {}}\n\n' +
      `event: done\ndata: ${JSON.stringify(DONE)}\n\n`,
  );
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.mocked(apiClient.get).mockResolvedValue({ providers: [], default: "openai" });
  fetchMock = vi.fn().mockResolvedValue(streamed());
  vi.stubGlobal("fetch", fetchMock);
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(apiClient.get).mockReset();
});

function sentBody(): Record<string, unknown> {
  return JSON.parse(fetchMock.mock.calls[0][1].body as string) as Record<string, unknown>;
}

describe("AssistantPanel", () => {
  it("asks the endpoint it is given, with its extra fields, and shows the answer", async () => {
    render(
      <AssistantPanel
        title="Asistente de alineación"
        endpoint="/lineup-assistant/12/6/ask/stream"
        intro="Pregunta por tu once."
        suggestions={["¿Juega Raphinha?"]}
        placeholder="Pregunta algo sobre tu alineación…"
        extraBody={{ extra: 1 }}
        historyLimit={40}
      />,
    );
    fireEvent.click(screen.getByText("¿Juega Raphinha?"));

    expect(await screen.findByText("Raphinha juega: FF 80 %.")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/lineup-assistant\/12\/6\/ask\/stream$/);
    expect(sentBody()).toMatchObject({ question: "¿Juega Raphinha?", history: [], extra: 1 });
    expect(screen.getByText(/consultó: mi_plantilla/)).toBeInTheDocument();
  });

  it("shows the backend's reason when the chat is refused", async () => {
    fetchMock.mockResolvedValue(
      new Response('{"message": "El asistente esta desactivado"}', { status: 422 }),
    );
    render(
      <AssistantPanel
        title="t"
        endpoint="/lineup-assistant/12/6/ask/stream"
        intro="i"
        suggestions={["hola"]}
        placeholder="p"
      />,
    );
    fireEvent.click(screen.getByText("hola"));
    expect(await screen.findByText("El asistente esta desactivado")).toBeInTheDocument();
  });
});

describe("the draft chat", () => {
  it("still asks the draft endpoint with the board's participation model", async () => {
    render(<DraftAssistantPanel seasonId={3} phase="preseason" />);
    expect(screen.getByText("Asistente de draft")).toBeInTheDocument();
    fireEvent.click(screen.getByText("¿A quién cojo en este pick?"));

    await screen.findByText("Raphinha juega: FF 80 %.");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/draft-assistant\/3\/preseason\/ask\/stream$/);
    expect(sentBody()).toHaveProperty("participacion");
  });
});
