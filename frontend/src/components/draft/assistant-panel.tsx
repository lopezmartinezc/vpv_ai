"use client";

import { useRef, useState } from "react";

import { apiClient, ApiClientError } from "@/lib/api-client";

interface Message {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
}

interface AskResponse {
  reply: string;
  provider: string;
  tool_calls: { name: string; arguments: Record<string, unknown> }[];
  truncated: boolean;
}

const SUGGESTIONS = [
  "¿A quién cojo en este pick?",
  "¿Aguanta este jugador hasta mi próximo turno?",
  "¿Por qué está tan arriba el primero de la lista?",
  "¿Quién va corto de qué posición?",
  "¿Cuántos porteros han salido ya?",
];

/**
 * Admin-only chat over the draft data. Every answer comes from the backend
 * querying the live board through the same services the UI uses, so the chat
 * cannot drift from what is on screen.
 */
export function AssistantPanel({
  seasonId,
  phase,
}: {
  seasonId: number;
  phase: string;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    // Send the whole conversation; the backend keeps the last 80 messages.
    // Slicing here to 10 made the assistant forget the thread after five
    // exchanges — during a draft that is most of the session.
    const history = messages.slice(-80).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await apiClient.post<AskResponse>(
        `/draft-assistant/${seasonId}/${phase}/ask`,
        { question: trimmed, history },
      );
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          tools: res.tool_calls.map((t) => t.name),
        },
      ]);
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.error.message
          : "No he podido contactar con el asistente.";
      setError(message);
    } finally {
      setLoading(false);
      requestAnimationFrame(() =>
        endRef.current?.scrollIntoView({ behavior: "smooth" }),
      );
    }
  }

  return (
    <details className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-vpv-text">
        Asistente de draft
      </summary>

      <div className="border-t border-vpv-card-border px-4 py-3">
        <div className="max-h-96 space-y-3 overflow-y-auto">
          {messages.length === 0 && (
            <div className="space-y-2">
              <p className="text-xs text-vpv-text-muted">
                Pregunta sobre el tablero. Consulta los datos en vivo; no opina
                por su cuenta.
              </p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => void send(s)}
                    className="rounded-full border border-vpv-card-border px-3 py-1 text-xs text-vpv-text-muted hover:text-vpv-text"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[85%] rounded-lg bg-vpv-accent/15 px-3 py-2 text-sm text-vpv-text"
                  : "mr-auto max-w-[95%] rounded-lg bg-vpv-bg px-3 py-2 text-sm text-vpv-text"
              }
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.tools && m.tools.length > 0 && (
                <p className="mt-1 text-[10px] text-vpv-text-muted">
                  consultó: {Array.from(new Set(m.tools)).join(", ")}
                </p>
              )}
            </div>
          ))}

          {loading && (
            <p className="text-xs text-vpv-text-muted">Consultando el tablero…</p>
          )}
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div ref={endRef} />
        </div>

        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void send(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={4000}
            placeholder="Pregunta algo sobre el draft…"
            className="flex-1 rounded-md border border-vpv-card-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-md bg-vpv-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            Enviar
          </button>
        </form>
      </div>
    </details>
  );
}
