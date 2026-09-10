"use client";
import { useState, type ReactElement } from "react";
import { AssistantPanel } from "@/components/draft/assistant-panel";
import type { PanelProps } from "./contracts";
import { ExperimentalPanel } from "./panel";

export function DraftChatExperiment(props: Omit<PanelProps, "active"> & {seasonId: number; phase: string}): ReactElement {
  const [version, setVersion] = useState<"legacy" | "v2">("legacy");
  const [visited, setVisited] = useState(false);
  return <section aria-label="Versiones del asistente" className="space-y-2">
    <div className="flex gap-2 text-sm" role="group" aria-label="Versión del chat">
      <button type="button" aria-pressed={version === "legacy"} onClick={() => setVersion("legacy")}>Actual</button>
      <button type="button" aria-pressed={version === "v2"} onClick={() => {setVisited(true); setVersion("v2");}}>Experimental V2</button>
    </div>
    <div hidden={version !== "legacy"}><AssistantPanel seasonId={props.seasonId} phase={props.phase} /></div>
    {visited && <div hidden={version !== "v2"}><ExperimentalPanel {...props} active={version === "v2"} /></div>}
  </section>;
}
