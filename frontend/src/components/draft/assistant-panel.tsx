"use client";

import { AssistantPanel as ChatPanel } from "@/components/assistant/assistant-panel";
import { useParticipationModel } from "@/lib/participation-model";

const SUGGESTIONS = [
  "¿A quién cojo en este pick?",
  "¿Aguanta este jugador hasta mi próximo turno?",
  "¿Por qué está tan arriba el primero de la lista?",
  "¿Quién va corto de qué posición?",
  "¿Cuántos porteros han salido ya?",
];

/**
 * Admin-only chat over the draft board. Every answer comes from the backend
 * querying the live board through the same services the UI uses, so the chat
 * cannot drift from what is on screen.
 */
export function AssistantPanel({
  seasonId,
  phase,
}: {
  seasonId: number;
  phase: string;
}) {
  const [participation] = useParticipationModel();
  return (
    <ChatPanel
      title="Asistente de draft"
      endpoint={`/draft-assistant/${seasonId}/${phase}/ask/stream`}
      intro="Pregunta sobre el tablero. Consulta los datos en vivo; no opina por su cuenta."
      suggestions={SUGGESTIONS}
      placeholder="Pregunta algo sobre el draft…"
      // The same model the board on screen is using, so the chat and the
      // table quote the same Prioridad. The whole draft conversation is sent:
      // cutting it to ten messages made the chat forget the thread mid-draft.
      extraBody={{ participacion: participation }}
      historyLimit={80}
    />
  );
}
