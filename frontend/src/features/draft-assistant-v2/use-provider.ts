"use client";
import type { Dispatch, SetStateAction } from "react";
import { useEffect, useState } from "react";
import { fetchV2 } from "./api";
import { capabilitiesSchema, type Capabilities } from "./contracts";

interface ProviderState { options: Capabilities | null; provider: "openai" | "anthropic"; setProvider: Dispatch<SetStateAction<"openai" | "anthropic">>; model: string; setModel: Dispatch<SetStateAction<string>>; error: string; }

export function useProvider(): ProviderState {
  const [options, setOptions] = useState<Capabilities | null>(null);
  const [provider, setProvider] = useState<"openai" | "anthropic">("openai");
  const [model, setModel] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchV2("/providers", { signal: controller.signal }).then((r) => r.json())
      .then((data: unknown) => {
        if (controller.signal.aborted) return;
        const parsed = capabilitiesSchema.parse(data); setOptions(parsed);
        const first = parsed.providers.find((p) => p.name === parsed.default) ?? parsed.providers[0];
        if (first) { setProvider(first.name); setModel(first.default_model); }
        if (!parsed.enabled || !first) setError("V2 desactivada o sin proveedores configurados.");
      }).catch(() => { if (!controller.signal.aborted) setError("No se pudo cargar la configuración V2."); });
    return () => controller.abort();
  }, []);
  return { options, provider, setProvider, model, setModel, error };
}
