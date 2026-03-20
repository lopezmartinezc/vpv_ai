"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { PERM, PERM_LABELS, hasPerm, type PermKey } from "@/lib/permissions";

interface AdminUser {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  is_admin: boolean;
  permissions: number;
  has_password: boolean;
  has_session: boolean;
  telegram_chat_id: string | null;
}


export default function AdminUsuariosPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState<number | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      const userData = await apiClient.get<AdminUser[]>("/auth/admin/users");
      setUsers(userData);
    } catch {
      // handled by auth context
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  async function handleToggleAdmin(userId: number) {
    setActionLoading(userId);
    setActionError(null);
    try {
      const updated = await apiClient.put<AdminUser>(
        `/auth/admin/users/${userId}/toggle-admin`,
        {},
      );
      setUsers((prev) =>
        prev.map((u) => (u.id === updated.id ? updated : u)),
      );
    } catch (e) {
      console.error("toggle-admin error:", e);
      setActionError(e instanceof Error ? e.message : "Error al cambiar admin");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleTogglePerm(userId: number, currentPerms: number, perm: number) {
    setActionLoading(userId);
    setActionError(null);
    const newPerms = currentPerms ^ perm; // XOR toggles the bit
    try {
      const updated = await apiClient.put<AdminUser>(
        `/auth/admin/users/${userId}/permissions`,
        { permissions: newPerms },
      );
      setUsers((prev) =>
        prev.map((u) => (u.id === updated.id ? updated : u)),
      );
    } catch (e) {
      console.error("set-permissions error:", e);
      setActionError(e instanceof Error ? e.message : "Error al cambiar permisos");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleForceLogout(userId: number) {
    setActionLoading(userId);
    setActionError(null);
    try {
      await apiClient.post<{ message: string }>(
        `/auth/admin/users/${userId}/force-logout`,
        {},
      );
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, has_session: false } : u)),
      );
    } catch (e) {
      console.error("force-logout error:", e);
      setActionError(e instanceof Error ? e.message : "Error al cerrar sesion");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleResetPassword(userId: number) {
    setActionLoading(userId);
    setActionError(null);
    try {
      const invite = await apiClient.post<{ token: string }>(
        `/auth/admin/users/${userId}/reset-password`,
        {},
      );
      const url = `${window.location.origin}/registro/${invite.token}`;
      await navigator.clipboard.writeText(url);
      setCopiedToken(userId);
      setTimeout(() => setCopiedToken(null), 3000);
    } catch (e) {
      console.error("reset-password error:", e);
      setActionError(e instanceof Error ? e.message : "Error al resetear password");
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
    {actionError && (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        {actionError}
      </div>
    )}
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
                {user.permissions > 0 && !user.is_admin && (
                  <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-medium text-blue-400">
                    Permisos
                  </span>
                )}
                {!user.has_password && (
                  <span className="rounded bg-vpv-danger/20 px-2 py-0.5 text-xs font-medium text-vpv-danger">
                    Sin password
                  </span>
                )}
                {user.has_session && (
                  <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-400">
                    Online
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
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
              {user.has_session && (
                <button
                  onClick={() => handleForceLogout(user.id)}
                  disabled={actionLoading === user.id}
                  className="rounded border border-red-500/30 px-2 py-1 text-xs text-red-400 transition-colors hover:bg-red-500/10 disabled:opacity-50"
                >
                  Cerrar sesion
                </button>
              )}
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
                    {user.permissions > 0 && !user.is_admin && (
                      <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-medium text-blue-400">
                        Permisos
                      </span>
                    )}
                    {!user.has_password && (
                      <span className="rounded bg-vpv-danger/20 px-2 py-0.5 text-xs font-medium text-vpv-danger">
                        Sin password
                      </span>
                    )}
                    {user.has_session && (
                      <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-400">
                        Online
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
                    {user.has_session && (
                      <button
                        onClick={() => handleForceLogout(user.id)}
                        disabled={actionLoading === user.id}
                        className="rounded border border-red-500/30 px-2 py-1 text-xs text-red-400 transition-colors hover:bg-red-500/10 disabled:opacity-50"
                      >
                        Cerrar sesion
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>

    {/* Permissions per user */}
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-border px-4 py-3">
        <h2 className="font-semibold text-vpv-text">Permisos</h2>
        <p className="text-xs text-vpv-text-muted">
          Los admins tienen acceso total. Los permisos solo aplican a usuarios no-admin.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-bg text-left text-vpv-text-muted">
              <th className="px-4 py-2">Usuario</th>
              {(Object.keys(PERM) as PermKey[]).map((key) => (
                <th key={key} className="px-2 py-2 text-center text-[10px]">
                  {PERM_LABELS[key]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users
              .filter((u) => !u.is_admin)
              .map((user) => (
                <tr
                  key={user.id}
                  className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/50"
                >
                  <td className="px-4 py-2 font-medium text-vpv-text">
                    {user.display_name}
                  </td>
                  {(Object.keys(PERM) as PermKey[]).map((key) => (
                    <td key={key} className="px-2 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={hasPerm(user.permissions, PERM[key])}
                        onChange={() =>
                          handleTogglePerm(user.id, user.permissions, PERM[key])
                        }
                        disabled={actionLoading === user.id}
                        className="h-4 w-4 rounded border-vpv-border bg-vpv-bg text-vpv-accent accent-vpv-accent disabled:opacity-50"
                      />
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>

    </div>
  );
}
