import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnswerCard } from "./answer-card";
import type { Answer } from "./contracts";

const answer = (cached?: number): Answer => ({
  text: "ok", cards: [], evidence_ids: [], status: "current", warnings: [],
  revision: { draft: "d", board: "b", at: new Date().toISOString(), pick_count: 20 },
  provider: "openai", model: "gpt-5",
  usage: { input_tokens: 29515, output_tokens: 3405, rounds: 6, tool_calls: 5, latency_ms: 77248,
    ...(cached === undefined ? {} : { cached_tokens: cached }) },
});

describe("consumption line", () => {
  it("shows how much of the input was served from cache — the real bill", () => {
    render(<AnswerCard answer={answer(18000)} revision={null} onSelect={vi.fn()} refresh={vi.fn()} />);
    expect(screen.getByText(/\(18000 en caché\)/)).toBeInTheDocument();
  });
  it("says nothing about cache when there was none, and parses an old answer without the field", () => {
    render(<AnswerCard answer={answer()} revision={null} onSelect={vi.fn()} refresh={vi.fn()} />);
    expect(screen.queryByText(/en caché/)).toBeNull();
    expect(screen.getByText(/29515 tokens entrada/)).toBeInTheDocument();
  });
});
