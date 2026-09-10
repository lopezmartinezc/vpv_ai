"use client";
import { useEffect, useState } from "react";
import { fetchV2 } from "./api";
import { revisionSchema, type Revision } from "./contracts";

export function useRevision(draftId: number, participation: string, enabled: boolean,
  trigger: string): Revision | null {
  const [revision, setRevision] = useState<Revision | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let running = false;
    const refresh = async (): Promise<void> => {
      if (running) return;
      running = true;
      try {
        const r = await fetchV2(`/${draftId}/revision?participation=${participation}`, { signal: controller.signal });
        const parsed = revisionSchema.parse(await r.json());
        if (!controller.signal.aborted) setRevision(parsed);
      } catch { if (!controller.signal.aborted) setRevision(null); }
      finally { running = false; }
    };
    void refresh(); const timer = setInterval(() => void refresh(), 30_000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [draftId, participation, enabled, trigger]);
  return revision;
}
