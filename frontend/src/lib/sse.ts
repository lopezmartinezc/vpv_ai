/**
 * Minimal Server-Sent Events reader over `fetch`.
 *
 * `EventSource` cannot send a POST body or an Authorization header, and the
 * assistant needs both, so the stream is read by hand. Frames are separated
 * by a blank line; each carries `event:` and `data:` lines. The parser is a
 * pure function over a text buffer so it can be tested without a network.
 */

export interface SseFrame {
  event: string;
  data: string;
}

/**
 * Split a buffer into complete frames, returning what is left over. A chunk
 * boundary can fall anywhere — mid-line, mid-frame — so the remainder must be
 * carried into the next call untouched.
 */
export function feedSse(buffer: string, chunk: string): { frames: SseFrame[]; rest: string } {
  const text = buffer + chunk;
  const parts = text.split("\n\n");
  const rest = parts.pop() ?? "";
  const frames: SseFrame[] = [];
  for (const raw of parts) {
    let event = "message";
    const data: string[] = [];
    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length > 0) frames.push({ event, data: data.join("\n") });
  }
  return { frames, rest };
}

/** Iterate the frames of a streaming `Response` as they arrive. */
export async function* readSse(response: Response): AsyncGenerator<SseFrame> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const out = feedSse(buffer, decoder.decode(value, { stream: true }));
    buffer = out.rest;
    for (const frame of out.frames) yield frame;
  }
  // A final frame without a trailing blank line is still a frame.
  const tail = feedSse(buffer, "\n\n");
  for (const frame of tail.frames) yield frame;
}
