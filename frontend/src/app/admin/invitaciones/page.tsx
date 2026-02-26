"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface UserWithoutPassword {
  id: number;
  username: string;
  display_name: string;
}

interface InviteEntry {
  id: number;
  token: string;
  target_user_id: number | null;
  target_display_name: string | null;
  created_by_display_name: string;
  expires_at: string;
  used_at: string | null;
  created_at: string;
}

export default function AdminInvitacionesPage() {
  const [invites, setInvites] = useState<InviteEntry[]>([]);
  const [usersWithout, setUsersWithout] = useState<UserWithoutPassword[]>([]);
  const [loading, setLoading] = useState(true);

  const [targetUserId, setTargetUserId] = useState<string>("");
  const [expiresDays, setExpiresDays] = useState(7);
  const [creating, setCreating] = useState(false);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [inv, users] = await Promise.all([
        apiClient.get<InviteEntry[]>("/auth/admin/invites"),
        apiClient.get<UserWithoutPassword[]>("/auth/admin/users-without-password"),
      ]);
      setInvites(inv);
      setUsersWithout(users);
    } catch {
      // unauthorized
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleCreate() {
    setCreating(true);
    try {
      await apiClient.post<InviteEntry>("/auth/admin/invite", {
        target_user_id: targetUserId ? Number(targetUserId) : null,
        expires_days: expiresDays,
      });
      setTargetUserId("");
      await fetchData();
    } catch {
      // error
    } finally {
      setCreating(false);
    }
  }

  function copyLink(token: string) {
    const baseUrl = window.location.origin;
    const url = `${baseUrl}/registro/${token}`;
    navigator.clipboard.writeText(url);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  }

  if (loading) {
    return (
      <div className="flex min-h-[20vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* Create invite */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
        <h2 className="mb-3 font-semibold text-vpv-text">Nueva invitacion</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-vpv-text-muted">
              Usuario destino (opcional)
            </label>
            <select
              value={targetUserId}
              onChange={(e) => setTargetUserId(e.target.value)}
              className="rounded-md border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text"
            >
              <option value="">Registro abierto</option>
              {usersWithout.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name} ({u.username})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-vpv-text-muted">
              Expira en (dias)
            </label>
            <input
              type="number"
              min={1}
              max={30}
              value={expiresDays}
              onChange={(e) => setExpiresDays(Number(e.target.value))}
              className="w-20 rounded-md border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="rounded-md bg-vpv-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-vpv-accent-hover disabled:opacity-50"
          >
            {creating ? "Creando..." : "Crear invitacion"}
          </button>
        </div>
      </div>

      {/* Invite list */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Invitaciones ({invites.length})
          </h2>
        </div>
        {invites.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-vpv-text-muted">
            No hay invitaciones
          </p>
        ) : (
          <div className="divide-y divide-vpv-border">
            {invites.map((inv) => {
              const isUsed = !!inv.used_at;
              const isExpired =
                !isUsed && new Date(inv.expires_at) < new Date();

              return (
                <div
                  key={inv.id}
                  className={`flex flex-wrap items-center gap-3 px-4 py-3 ${isUsed || isExpired ? "opacity-50" : ""}`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-vpv-text">
                      {inv.target_display_name || "Registro abierto"}
                    </p>
                    <p className="text-xs text-vpv-text-muted">
                      Creada por {inv.created_by_display_name} &middot;{" "}
                      {new Date(inv.created_at).toLocaleDateString("es-ES")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {isUsed ? (
                      <span className="rounded bg-vpv-success/20 px-2 py-0.5 text-xs font-medium text-vpv-success">
                        Usada
                      </span>
                    ) : isExpired ? (
                      <span className="rounded bg-vpv-danger/20 px-2 py-0.5 text-xs font-medium text-vpv-danger">
                        Expirada
                      </span>
                    ) : (
                      <>
                        <span className="rounded bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                          Activa
                        </span>
                        <button
                          onClick={() => copyLink(inv.token)}
                          className="rounded-md border border-vpv-border px-2 py-1 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text"
                        >
                          {copiedToken === inv.token ? "Copiado!" : "Copiar enlace"}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
