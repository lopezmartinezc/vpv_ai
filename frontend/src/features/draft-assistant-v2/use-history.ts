"use client";
import type { Dispatch, SetStateAction } from "react";
import { useCallback, useEffect, useState } from "react";
import { fetchV2 } from "./api";
import { historySchema, type History } from "./contracts";

interface HistoryState { history: History; setHistory: Dispatch<SetStateAction<History>>; ready: boolean; error: string; clear: () => Promise<void>; }

export function useHistory(draftId: number): HistoryState {
  const [history, setHistory] = useState<History>({ exchanges: [] });
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchV2(`/${draftId}/history`, { signal: controller.signal })
      .then((r) => r.json()).then((data: unknown) => {
        if (!controller.signal.aborted) { setHistory(historySchema.parse(data)); setReady(true); }
      }).catch(() => { if (!controller.signal.aborted) setError("No se pudo cargar el historial V2. Comprueba la migración."); });
    return () => controller.abort();
  }, [draftId]);
  const clear = useCallback(async (): Promise<void> => {
    try { await fetchV2(`/${draftId}/history`, { method: "DELETE" }); setHistory({ exchanges: [] }); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo borrar."); }
  }, [draftId]);
  return { history, setHistory, ready, error, clear };
}
