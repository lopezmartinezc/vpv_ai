import { act, fireEvent, render, screen } from "@testing-library/react";
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
  fetchMock = vi.fn().mockImplementation(() => Promise.resolve(streamed()));
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
  it("aborts a pending request on unmount and ignores its late answer", async () => {
    let resolve: (response: Response) => void = () => {
      throw new Error("Not started");
    };
    fetchMock.mockReturnValue(
      new Promise<Response>((done) => {
        resolve = done;
      }),
    );
    const view = render(
      <AssistantPanel title="t" endpoint="/old" intro="i" suggestions={["hola"]} placeholder="p" />,
    );
    fireEvent.click(screen.getByText("hola"));
    const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
    expect(signal.aborted).toBe(false);
    view.unmount();
    expect(signal.aborted).toBe(true);
    render(
      <AssistantPanel title="t" endpoint="/new" intro="i" suggestions={["hola"]} placeholder="p" />,
    );
    await act(async () => {
      resolve(streamed());
    });
    expect(screen.queryByText(DONE.reply)).not.toBeInTheDocument();
  });

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

function panel(): void {
  render(
    <AssistantPanel title="t" endpoint="/e" intro="i" suggestions={["hola"]} placeholder="p" />,
  );
}

function pending(): (response: Response) => void {
  let resolve: (response: Response) => void = () => {
    throw new Error("Not started");
  };
  fetchMock.mockReturnValueOnce(
    new Promise<Response>((done) => {
      resolve = done;
    }),
  );
  return () => resolve;
}

describe("controls", () => {
  it("stops a question in flight and offers to retry it without repeating it", async () => {
    const resolve = pending();
    panel();
    fireEvent.click(screen.getByText("hola"));
    expect(screen.getByText("Pensando…")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Detener" }));
    expect((fetchMock.mock.calls[0][1].signal as AbortSignal).aborted).toBe(true);
    expect(screen.queryByText("Pensando…")).not.toBeInTheDocument();
    expect(screen.getByText("Respuesta detenida.")).toBeInTheDocument();
    fetchMock.mockResolvedValueOnce(streamed());
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(DONE.reply)).toBeInTheDocument();
    expect(screen.getAllByText("hola")).toHaveLength(1);
    const retried = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(retried).toMatchObject({ question: "hola", history: [] });
    void resolve;
  });

  it("offers to retry after a failure", async () => {
    fetchMock.mockResolvedValueOnce(new Response('{"message": "Falta la clave"}', { status: 422 }));
    panel();
    fireEvent.click(screen.getByText("hola"));
    expect(await screen.findByText("Falta la clave")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(DONE.reply)).toBeInTheDocument();
    expect(screen.queryByText("Falta la clave")).not.toBeInTheDocument();
  });

  it("marks an answer the round cap cut short", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(`event: done\ndata: ${JSON.stringify({ ...DONE, truncated: true })}\n\n`),
    );
    panel();
    fireEvent.click(screen.getByText("hola"));
    expect(await screen.findByText(DONE.reply)).toBeInTheDocument();
    expect(screen.getByText(/Respuesta incompleta/)).toBeInTheDocument();
  });

  it("treats an empty answer as a failure, with retry", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(`event: done\ndata: ${JSON.stringify({ ...DONE, reply: "  " })}\n\n`),
    );
    panel();
    fireEvent.click(screen.getByText("hola"));
    expect(await screen.findByText("El asistente no ha respondido.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("starts a new conversation, dropping history and any question in flight", async () => {
    panel();
    fireEvent.click(screen.getByText("hola"));
    expect(await screen.findByText(DONE.reply)).toBeInTheDocument();
    pending();
    fireEvent.change(screen.getByLabelText("p"), { target: { value: "otra" } });
    fireEvent.submit(screen.getByLabelText("p").closest("form")!);
    expect(screen.getByText("Pensando…")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Nueva conversación" }));
    expect((fetchMock.mock.calls[1][1].signal as AbortSignal).aborted).toBe(true);
    expect(screen.queryByText(DONE.reply)).not.toBeInTheDocument();
    expect(screen.queryByText("otra")).not.toBeInTheDocument();
    expect(screen.getByText("i")).toBeInTheDocument();
    fireEvent.click(screen.getByText("hola"));
    expect(JSON.parse(fetchMock.mock.calls[2][1].body as string)).toMatchObject({ history: [] });
    await screen.findByText(DONE.reply);
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

it("stopping the retried request still aborts it after the old request finishes", async () => {
  let finishOld!: (r: Response) => void;
  const first = new Promise<Response>((r) => {
    finishOld = r;
  });
  const second = new Promise<Response>(() => {});
  const fetchMock = vi.fn().mockReturnValueOnce(first).mockReturnValueOnce(second);
  vi.stubGlobal("fetch", fetchMock);
  Element.prototype.scrollIntoView = vi.fn();
  render(
    <AssistantPanel title="t" endpoint="/test" intro="i" suggestions={["hola"]} placeholder="p" />,
  );
  fireEvent.click(screen.getByText("hola"));
  fireEvent.click(screen.getByRole("button", { name: "Detener" }));
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  const signal = fetchMock.mock.calls[1][1].signal as AbortSignal;
  await act(async () => {
    finishOld(new Response("event: done\ndata: {}\n\n"));
  });
  fireEvent.click(screen.getByRole("button", { name: "Detener" }));
  expect(signal.aborted).toBe(true);
});

it("never selects a default absent from the offered models", async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    providers: [{ name: "openai", default_model: "retired", models: ["available"] }],
    default: "openai",
  });
  render(
    <AssistantPanel title="t" endpoint="/test" intro="i" suggestions={["hola"]} placeholder="p" />,
  );
  expect(await screen.findByRole("combobox", { name: "Modelo" })).toHaveValue("available");
  fireEvent.click(screen.getByText("hola"));
  await screen.findByText(DONE.reply);
  expect(sentBody()).toHaveProperty("model", "available");
});
