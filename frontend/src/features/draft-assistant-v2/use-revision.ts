"use client";
import { useEffect, useState } from "react";
import { fetchV2 } from "./api";
import { revisionSchema, type Revision } from "./contracts";

export function useRevision(draftId: number, participation: string, enabled: boolean,
  trigger: string): Revision | null {
  const key = JSON.stringify([draftId, participation, trigger]);
  const [checked, setChecked] = useState<{key: string; revision: Revision} | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let running = false;
    const refresh = async (): Promise<void> => {
      if (running) return;
      running = true;
      setChecked(null);
      try {
        const r = await fetchV2(`/${draftId}/revision?participation=${participation}`, { signal: controller.signal });
        const parsed = revisionSchema.parse(await r.json());
        if (!controller.signal.aborted) setChecked({key, revision: parsed});
      } catch { if (!controller.signal.aborted) setChecked(null); }
      finally { running = false; }
    };
    void refresh(); const timer = setInterval(() => void refresh(), 30_000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [draftId, participation, enabled, trigger, key]);
  return enabled && checked?.key === key ? checked.revision : null;
}
