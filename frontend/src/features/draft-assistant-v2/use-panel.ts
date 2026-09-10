"use client";
import type { Dispatch, SetStateAction } from "react";
import { useCallback, useState } from "react";
import { useParticipationModel } from "@/lib/participation-model";
import type { Answer, Ask, PanelProps } from "./contracts";
import { useHistory } from "./use-history";
import { useProvider } from "./use-provider";
import { useQuestion } from "./use-question";
import { useRevision } from "./use-revision";

interface PanelState { input: string; setInput: Dispatch<SetStateAction<string>>; mode: Ask["mode"]; setMode: Dispatch<SetStateAction<Ask["mode"]>>; target: number | null; setTarget: Dispatch<SetStateAction<number | null>>; selected: number[]; setSelected: Dispatch<SetStateAction<number[]>>; saved: ReturnType<typeof useHistory>; provider: ReturnType<typeof useProvider>; query: ReturnType<typeof useQuestion>; revision: ReturnType<typeof useRevision>; send: (question: string) => void; }

export function usePanel(props: PanelProps): PanelState {
  const [participation] = useParticipationModel();
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Ask["mode"]>("quick");
  const [target, setTarget] = useState<number | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const saved = useHistory(props.draftId);
  const provider = useProvider();
  const { setHistory } = saved;
  const onAnswer = useCallback((question: string, answer: Answer): void => {
    setHistory((h) => ({exchanges: [...h.exchanges.slice(-39), {question, answer}]}));
  }, [setHistory]);
  const query = useQuestion(props.draftId, props.active, onAnswer);
  const revision = useRevision(props.draftId, participation, props.active && saved.history.exchanges.length > 0,
    props.liveToken + String(saved.history.exchanges.length));
  const send = (question: string): void => { void query.send({question, mode, participation,
    provider: provider.provider, model: provider.model,
    context: {...props.context, participant_id: target,
      selected_player_ids: selected.length ? selected : props.context.selected_player_ids}}); };
  return {input, setInput, mode, setMode, target, setTarget, selected, setSelected, saved, provider, query, revision, send};
}
