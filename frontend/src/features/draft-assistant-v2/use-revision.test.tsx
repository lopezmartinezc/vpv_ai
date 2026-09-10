import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { fetchV2 } from "./api";
import { useRevision } from "./use-revision";

vi.mock("./api", () => ({ fetchV2: vi.fn() }));
afterEach(() => vi.clearAllMocks());
const revision = {draft: "first", board: "board", at: "2026-09-10T00:00:00Z", pick_count: 1};

it("invalidates immediately on a new pick, then accepts only the new revision", async () => {
  vi.mocked(fetchV2).mockResolvedValueOnce(new Response(JSON.stringify(revision)));
  const {result, rerender} = renderHook(({trigger}) => useRevision(1, "mixto", true, trigger),
    {initialProps: {trigger: "pick1"}});
  await waitFor(() => expect(result.current?.draft).toBe("first"));
  let resolve!: (response: Response) => void;
  vi.mocked(fetchV2).mockImplementationOnce(() => new Promise((done) => {resolve = done;}));
  rerender({trigger: "pick2"});
  expect(result.current).toBeNull();
  await act(async () => resolve(new Response(JSON.stringify({...revision, draft: "second"}))));
  await waitFor(() => expect(result.current?.draft).toBe("second"));
});

it("does not preserve confirmed availability when verification fails", async () => {
  vi.mocked(fetchV2).mockRejectedValueOnce(new Error("offline"));
  const {result} = renderHook(() => useRevision(1, "mixto", true, "pick"));
  await waitFor(() => expect(fetchV2).toHaveBeenCalled());
  expect(result.current).toBeNull();
});
