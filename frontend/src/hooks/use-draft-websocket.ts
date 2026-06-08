"use client";

import { useEffect, useRef, useState } from "react";

export interface DraftWSEvent {
  type:
    | "pick_added"
    | "pick_deleted"
    | "connected"
    | "online_count"
    | "draft_completed"
    | "draft_status_changed";
  status?: string;
  pick?: {
    pick_number: number;
    round_number: number;
    participant_id: number;
    player_id: number;
    display_name: string;
    player_name: string;
    position: string;
    team_name: string;
    photo_path?: string | null;
    origin?: "manual" | "auto";
  };
  // pick_deleted payload
  pick_number?: number;
  participant_id?: number;
  player_id?: number;
  next_pick_number?: number;
  // shared
  next_participant_id?: number;
  participants_online?: number;
  draft_id?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

function getWsUrl(draftId: number, token: string): string {
  // When NEXT_PUBLIC_API_URL is an absolute URL (e.g. on staging where
  // it's set to "https://new.ligavpv.com/api"), just swap http(s) for
  // ws(s). Concatenating it to the current origin would duplicate the
  // host and produce an invalid URL like
  //   wss://new.ligavpv.comhttps://new.ligavpv.com/api/...
  if (/^https?:\/\//.test(API_BASE)) {
    const wsBase = API_BASE.replace(/^http/, "ws");
    return `${wsBase}/drafts/ws/${draftId}?token=${token}`;
  }
  const base = typeof window !== "undefined" ? window.location.origin : "";
  const wsProto = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "");
  return `${wsProto}://${host}${API_BASE}/drafts/ws/${draftId}?token=${token}`;
}

export function useDraftWebSocket(
  draftId: number | null,
  onEvent: (event: DraftWSEvent) => void,
) {
  const [online, setOnline] = useState(0);
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  });

  useEffect(() => {
    if (!draftId || typeof window === "undefined") return;
    const token = localStorage.getItem("vpv_token");
    if (!token) return;

    let ws: WebSocket | null = null;
    let closed = false;

    function open() {
      if (closed) return;
      const url = getWsUrl(draftId!, token!);
      ws = new WebSocket(url);

      ws.onopen = () => setConnected(true);

      ws.onmessage = (e) => {
        try {
          const data: DraftWSEvent = JSON.parse(e.data);
          if (data.participants_online !== undefined) {
            setOnline(data.participants_online);
          }
          onEventRef.current(data);
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(open, 3000);
      };

      ws.onerror = () => ws?.close();
    }

    open();

    return () => {
      closed = true;
      ws?.close();
    };
  }, [draftId]);

  return { online, connected };
}
