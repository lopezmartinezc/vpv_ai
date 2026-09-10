"use client";
import { useState, type ReactElement } from "react";
import { AssistantPanel } from "@/components/draft/assistant-panel";
import type { PanelProps } from "./contracts";
import { ExperimentalPanel } from "./panel";

type Version = "legacy" | "v2";

const TABS: { id: Version; label: string; hint: string }[] = [
  { id: "legacy", label: "Actual", hint: "El asistente en uso. Conserva su conversación al cambiar de pestaña." },
  { id: "v2", label: "Experimental V2", hint: "En pruebas. Tarjetas numéricas verificadas por el servidor e historial propio." },
];

export function DraftChatExperiment(
  props: Omit<PanelProps, "active"> & { seasonId: number; phase: string },
): ReactElement {
  const [version, setVersion] = useState<Version>("legacy");
  // V2 only mounts once its tab has been opened, and the current panel is never
  // unmounted — switching tabs must not cost anyone a conversation mid-draft.
  const [visited, setVisited] = useState(false);

  return (
    <section aria-label="Versiones del asistente" className="space-y-2">
      <div className="flex items-center gap-2">
        <div
          role="group"
          aria-label="Versión del chat"
          className="flex overflow-hidden rounded-md border border-vpv-card-border"
        >
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              aria-pressed={version === tab.id}
              title={tab.hint}
              onClick={() => {
                if (tab.id === "v2") setVisited(true);
                setVersion(tab.id);
              }}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                version === tab.id
                  ? "bg-vpv-accent text-white"
                  : "text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {version === "v2" && (
          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
            En pruebas
          </span>
        )}
      </div>

      {/* Both panels stay in the tree; `hidden` keeps the inactive one's state.
          Do not give these wrappers a class that sets `display` — it would win
          over the attribute and leave the hidden panel on screen. */}
      <div hidden={version !== "legacy"}>
        <AssistantPanel seasonId={props.seasonId} phase={props.phase} />
      </div>
      {visited && (
        <div hidden={version !== "v2"}>
          <ExperimentalPanel {...props} active={version === "v2"} />
        </div>
      )}
    </section>
  );
}
