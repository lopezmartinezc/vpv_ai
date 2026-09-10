import { z } from "zod";
import { API_BASE_URL } from "@/lib/api-client";
import { readSse } from "@/lib/sse";
import { answerSchema, askSchema, type Answer, type Ask } from "./contracts";

const errorSchema = z.object({ message: z.string() });
const progressSchema = z.object({ name: z.string() });

export async function fetchV2(path: string, options: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem("vpv_token");
  const response = await fetch(`${API_BASE_URL}/draft-assistant-v2${path}`, {
    ...options, headers: { "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) {
    const parsed = errorSchema.safeParse(await response.json().catch(() => null));
    throw new Error(parsed.success ? parsed.data.message : "V2 no disponible. Comprueba su configuración y migración.");
  }
  return response;
}

export async function askV2(draftId: number, request: Ask, signal: AbortSignal,
  progress: (name: string) => void): Promise<Answer> {
  const body = askSchema.parse(request);
  const response = await fetchV2(`/${draftId}/ask/stream`, {
    method: "POST", body: JSON.stringify(body), signal,
  });
  let answer: Answer | null = null;
  for await (const frame of readSse(response)) {
    const data: unknown = JSON.parse(frame.data);
    if (frame.event === "progress") progress(progressSchema.parse(data).name);
    if (frame.event === "done") answer = answerSchema.parse(data);
    if (frame.event === "error") throw new Error(errorSchema.parse(data).message);
  }
  if (!answer) throw new Error("La conexión terminó sin respuesta. Puedes reintentar.");
  return answer;
}
