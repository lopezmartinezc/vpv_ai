"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { askV2 } from "./api";
import type { Answer, Ask } from "./contracts";

interface QuestionState { loading: boolean; progress: string; error: string; lastQuestion: string; send: (request: Ask) => Promise<void>; cancel: () => void; }

export function useQuestion(draftId: number, active: boolean, onAnswer: (q: string, a: Answer) => void): QuestionState {
  const abort = useRef<AbortController | null>(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  useEffect(() => { if (!active) abort.current?.abort(); return () => abort.current?.abort(); }, [active]);
  const cancel = useCallback((): void => { abort.current?.abort(); }, []);
  const send = useCallback(async (request: Ask): Promise<void> => {
    if (abort.current || !active) return;
    const controller = new AbortController(); abort.current = controller;
    const timeout = setTimeout(() => controller.abort(), 190_000);
    setLoading(true); setError(""); setProgress("Leyendo contexto…"); setLastQuestion(request.question);
    try {
      const answer = await askV2(draftId, request, controller.signal, setProgress);
      if (!controller.signal.aborted) onAnswer(request.question, answer);
    } catch (err) {
      setError(controller.signal.aborted ? "Consulta cancelada. Puedes reintentar."
        : err instanceof Error ? err.message : "No se pudo completar la consulta.");
    } finally { clearTimeout(timeout); abort.current = null; setLoading(false); setProgress(""); }
  }, [active, draftId, onAnswer]);
  return { loading, progress, error, lastQuestion, send, cancel };
}
