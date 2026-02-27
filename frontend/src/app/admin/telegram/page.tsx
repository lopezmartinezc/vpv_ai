"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";

interface TelegramStatus {
  enabled: boolean;
  chat_id: string | null;
  bot_configured: boolean;
}

export default function AdminTelegramPage() {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [messageText, setMessageText] = useState("");
  const [lineupId, setLineupId] = useState("");

  // Fetch status on mount
  useState(() => {
    apiClient
      .get<TelegramStatus>("/telegram/admin/status")
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false));
  });

  async function handleSendMessage() {
    if (!messageText.trim()) return;
    setActionLoading("message");
    setResult(null);
    try {
      const data = await apiClient.post<{ sent: boolean }>(
        "/telegram/admin/send-message",
        { text: messageText },
      );
      setResult(data.sent ? "Mensaje enviado" : "Error al enviar mensaje");
      if (data.sent) setMessageText("");
    } catch {
      setResult("Error al enviar mensaje");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleSendLineup() {
    if (!lineupId.trim()) return;
    setActionLoading("lineup");
    setResult(null);
    try {
      const data = await apiClient.post<{ sent: boolean; lineup_id: number }>(
        `/telegram/admin/send-lineup/${lineupId}`,
        {},
      );
      setResult(
        data.sent
          ? `Alineacion ${data.lineup_id} enviada`
          : `Error al enviar alineacion ${lineupId}`,
      );
    } catch {
      setResult("Error al enviar alineacion");
    } finally {
      setActionLoading(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 py-4">
        <div className="h-32 animate-pulse rounded-lg bg-vpv-border" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Status */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">Estado del bot</h2>
        </div>
        <div className="space-y-2 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span
                className={`h-3 w-3 rounded-full ${status?.enabled ? "bg-green-500" : "bg-red-500"}`}
              />
              <span className="text-sm font-medium text-vpv-text">
                {status?.enabled ? "Habilitado" : "Deshabilitado"}
              </span>
            </div>
            {status?.bot_configured ? (
              <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs text-green-400">
                Bot configurado
              </span>
            ) : (
              <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                Token no configurado
              </span>
            )}
          </div>
          {status?.chat_id && (
            <p className="text-xs text-vpv-text-muted">
              Chat ID: {status.chat_id}
            </p>
          )}
          {!status?.enabled && (
            <p className="text-xs text-vpv-text-muted">
              Configura TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID y
              TELEGRAM_ENABLED=true en .env
            </p>
          )}
        </div>
      </div>

      {/* Send message */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Enviar mensaje al grupo
          </h2>
        </div>
        <div className="space-y-3 px-4 py-3">
          <textarea
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            placeholder="Escribe un mensaje (HTML permitido)..."
            rows={3}
            className="w-full rounded border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text placeholder:text-vpv-text-muted"
          />
          <button
            onClick={handleSendMessage}
            disabled={actionLoading !== null || !messageText.trim()}
            className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
          >
            {actionLoading === "message" ? "Enviando..." : "Enviar mensaje"}
          </button>
        </div>
      </div>

      {/* Re-send lineup */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Re-enviar alineacion
          </h2>
        </div>
        <div className="flex flex-wrap items-end gap-3 px-4 py-3">
          <div>
            <label className="mb-1 block text-xs text-vpv-text-muted">
              Lineup ID
            </label>
            <input
              type="number"
              value={lineupId}
              onChange={(e) => setLineupId(e.target.value)}
              className="w-24 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
            />
          </div>
          <button
            onClick={handleSendLineup}
            disabled={actionLoading !== null || !lineupId.trim()}
            className="rounded border border-vpv-border px-3 py-1.5 text-xs font-medium text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
          >
            {actionLoading === "lineup" ? "Enviando..." : "Re-enviar"}
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="rounded bg-vpv-bg px-3 py-2 text-sm text-vpv-text">
          {result}
        </div>
      )}
    </div>
  );
}
