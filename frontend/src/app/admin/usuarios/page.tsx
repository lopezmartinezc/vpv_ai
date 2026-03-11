"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface AdminUser {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  is_admin: boolean;
  has_password: boolean;
  telegram_chat_id: string | null;
}

interface SeasonSummary {
  id: number;
  name: string;
  status: string;
  matchday_current: number;
  total_participants: number;
}

interface SeasonParticipant {
  id: number;
  user_id: number;
  display_name: string;
  draft_order: number | null;
  is_active: boolean;
}

export default function AdminUsuariosPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [copiedToken, setCopiedToken] = useState<number | null>(null);

  // Season participants state
  const [seasons, setSeasons] = useState<SeasonSummary[]>([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);
  const [participants, setParticipants] = useState<SeasonParticipant[]>([]);
  const [participantsLoading, setParticipantsLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      const [userData, seasonData] = await Promise.all([
        apiClient.get<AdminUser[]>("/auth/admin/users"),
        apiClient.get<SeasonSummary[]>("/seasons"),
      ]);
      setUsers(userData);
      setSeasons(seasonData);
      if (seasonData.length > 0 && selectedSeasonId === null) {
        const active =
          seasonData.find((s) => s.status === "active") ?? seasonData[0];
        setSelectedSeasonId(active.id);
      }
    } catch {
      // handled by auth context
    } finally {
      setLoading(false);
    }
  }, [selectedSeasonId]);

  const fetchParticipants = useCallback(async (seasonId: number) => {
    setParticipantsLoading(true);
    try {
      const data = await apiClient.get<SeasonParticipant[]>(
        `/seasons/${seasonId}/participants`,
      );
      setParticipants(data);
    } catch {
      setParticipants([]);
    } finally {
      setParticipantsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    if (selectedSeasonId !== null) {
      fetchParticipants(selectedSeasonId);
    }
  }, [selectedSeasonId, fetchParticipants]);

  async function handleToggleActive(participantId: number) {
    if (selectedSeasonId === null) return;
    setTogglingId(participantId);
    try {
      const updated = await apiClient.put<SeasonParticipant>(
        `/seasons/admin/${selectedSeasonId}/participants/${participantId}/toggle-active`,
        {},
      );
      setParticipants((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p)),
      );
    } catch {
      // error
    } finally {
      setTogglingId(null);
    }
  }

  async function handleToggleAdmin(userId: number) {
    setActionLoading(userId);
    try {
      const updated = await apiClient.put<AdminUser>(
        `/auth/admin/users/${userId}/toggle-admin`,
        {},
      );
      setUsers((prev) =>
        prev.map((u) => (u.id === updated.id ? updated : u)),
      );
    } catch {
      // error
    } finally {
      setActionLoading(null);
    }
  }

  async function handleResetPassword(userId: number) {
    setActionLoading(userId);
    try {
      const invite = await apiClient.post<{ token: string }>(
        `/auth/admin/users/${userId}/reset-password`,
        {},
      );
      const url = `${window.location.origin}/registro/${invite.token}`;
      await navigator.clipboard.writeText(url);
      setCopiedToken(userId);
      setTimeout(() => setCopiedToken(null), 3000);
    } catch {
      // error
    } finally {
      setActionLoading(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-12 animate-pulse rounded-lg bg-vpv-border"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-border px-4 py-3">
        <h2 className="font-semibold text-vpv-text">
          Usuarios ({users.length})
        </h2>
      </div>

      {/* Mobile: Cards */}
      <div className="divide-y divide-vpv-border md:hidden">
        {users.map((user) => (
          <div key={user.id} className="space-y-2 px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-vpv-text">
                  {user.display_name}
                </p>
                <p className="text-xs text-vpv-text-muted">{user.username}</p>
              </div>
              <div className="flex items-center gap-2">
                {user.is_admin && (
                  <span className="rounded bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                    Admin
                  </span>
                )}
                {!user.has_password && (
                  <span className="rounded bg-vpv-danger/20 px-2 py-0.5 text-xs font-medium text-vpv-danger">
                    Sin password
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleToggleAdmin(user.id)}
                disabled={actionLoading === user.id}
                className="rounded border border-vpv-border px-2 py-1 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
              >
                {user.is_admin ? "Quitar admin" : "Hacer admin"}
              </button>
              <button
                onClick={() => handleResetPassword(user.id)}
                disabled={actionLoading === user.id}
                className="rounded border border-vpv-border px-2 py-1 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
              >
                {copiedToken === user.id
                  ? "Enlace copiado!"
                  : "Reset password"}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
              <th className="px-4 py-2">Usuario</th>
              <th className="px-4 py-2">Nombre</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr
                key={user.id}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
              >
                <td className="px-4 py-2 font-medium text-vpv-text">
                  {user.username}
                </td>
                <td className="px-4 py-2 text-vpv-text-muted">
                  {user.display_name}
                </td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-2">
                    {user.is_admin && (
                      <span className="rounded bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                        Admin
                      </span>
                    )}
                    {!user.has_password && (
                      <span className="rounded bg-vpv-danger/20 px-2 py-0.5 text-xs font-medium text-vpv-danger">
                        Sin password
                      </span>
                    )}
                    {user.has_password && !user.is_admin && (
                      <span className="text-xs text-vpv-text-muted">
                        Activo
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-2 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => handleToggleAdmin(user.id)}
                      disabled={actionLoading === user.id}
                      className="rounded border border-vpv-border px-2 py-1 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
                    >
                      {user.is_admin ? "Quitar admin" : "Hacer admin"}
                    </button>
                    <button
                      onClick={() => handleResetPassword(user.id)}
                      disabled={actionLoading === user.id}
                      className="rounded border border-vpv-border px-2 py-1 text-xs text-vpv-text-muted transition-colors hover:text-vpv-text disabled:opacity-50"
                    >
                      {copiedToken === user.id
                        ? "Enlace copiado!"
                        : "Reset password"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>

    {/* Season Participants */}
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-center justify-between border-b border-vpv-border px-4 py-3">
        <h2 className="font-semibold text-vpv-text">
          Participantes por temporada
        </h2>
        <select
          value={selectedSeasonId ?? ""}
          onChange={(e) => setSelectedSeasonId(Number(e.target.value))}
          className="rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text"
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {participantsLoading ? (
        <div className="space-y-2 p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded bg-vpv-border"
            />
          ))}
        </div>
      ) : (
        <>
          {/* Mobile: Cards */}
          <div className="divide-y divide-vpv-border md:hidden">
            {participants.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <div>
                  <p
                    className={`font-medium ${p.is_active ? "text-vpv-text" : "text-vpv-text-muted line-through"}`}
                  >
                    {p.display_name}
                  </p>
                  <p className="text-xs text-vpv-text-muted">
                    {p.draft_order !== null
                      ? `Draft #${p.draft_order}`
                      : "Sin orden"}
                  </p>
                </div>
                <button
                  onClick={() => handleToggleActive(p.id)}
                  disabled={togglingId === p.id}
                  className={`rounded px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                    p.is_active
                      ? "border border-vpv-danger/30 text-vpv-danger hover:bg-vpv-danger/10"
                      : "border border-green-500/30 text-green-600 hover:bg-green-500/10"
                  }`}
                >
                  {p.is_active ? "Desactivar" : "Activar"}
                </button>
              </div>
            ))}
          </div>

          {/* Desktop: Table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
                  <th className="px-4 py-2">Nombre</th>
                  <th className="px-4 py-2">Orden draft</th>
                  <th className="px-4 py-2">Estado</th>
                  <th className="px-4 py-2 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {participants.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                  >
                    <td
                      className={`px-4 py-2 font-medium ${p.is_active ? "text-vpv-text" : "text-vpv-text-muted line-through"}`}
                    >
                      {p.display_name}
                    </td>
                    <td className="px-4 py-2 text-vpv-text-muted">
                      {p.draft_order !== null ? `#${p.draft_order}` : "—"}
                    </td>
                    <td className="px-4 py-2">
                      {p.is_active ? (
                        <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-600">
                          Activo
                        </span>
                      ) : (
                        <span className="rounded bg-vpv-danger/20 px-2 py-0.5 text-xs font-medium text-vpv-danger">
                          Inactivo
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => handleToggleActive(p.id)}
                        disabled={togglingId === p.id}
                        className={`rounded px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                          p.is_active
                            ? "border border-vpv-danger/30 text-vpv-danger hover:bg-vpv-danger/10"
                            : "border border-green-500/30 text-green-600 hover:bg-green-500/10"
                        }`}
                      >
                        {p.is_active ? "Desactivar" : "Activar"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {participants.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-vpv-text-muted">
              No hay participantes en esta temporada
            </p>
          )}
        </>
      )}
    </div>
    </div>
  );
}
