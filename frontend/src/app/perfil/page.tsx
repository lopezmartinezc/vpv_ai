"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient } from "@/lib/api-client";
import { PersonalEvolution } from "@/components/standings/personal-evolution";
import type { EvolutionEntry } from "@/types";

interface EvolutionResponse {
  season_id: number;
  entries: EvolutionEntry[];
}

interface MeResponse {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  is_admin: boolean;
  is_draft_manager: boolean;
}

export default function PerfilPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason } = useSeason();
  const { data: me } = useFetch<MeResponse>(user ? "/auth/me" : null);
  const { data: evolution } = useFetch<EvolutionResponse>(
    selectedSeason ? `/standings/${selectedSeason.id}/evolution` : null,
  );

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  if (authLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    router.push("/login");
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword.length < 8) {
      setError("La nueva contraseña debe tener al menos 8 caracteres");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Las contraseñas no coinciden");
      return;
    }
    if (currentPassword === newPassword) {
      setError("La nueva contraseña debe ser diferente a la actual");
      return;
    }

    setSaving(true);
    try {
      await apiClient.put<{ message: string }>("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccess("Contraseña actualizada correctamente");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Error al cambiar la contraseña",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-vpv-text">Mi perfil</h1>

      {/* User info */}
      <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-vpv-text-muted">Usuario</span>
            <span className="font-medium text-vpv-text">{user.username}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-vpv-text-muted">Nombre</span>
            <span className="font-medium text-vpv-text">
              {me?.display_name ?? user.displayName}
            </span>
          </div>
          {user.isAdmin && (
            <div className="flex justify-between">
              <span className="text-vpv-text-muted">Rol</span>
              <span className="rounded-full bg-vpv-accent/20 px-2 py-0.5 text-xs font-medium text-vpv-accent">
                Admin
              </span>
            </div>
          )}
        </div>
      </section>

      {/* Evolution */}
      {evolution && evolution.entries.length > 0 && me && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-vpv-text">
            Mi temporada {selectedSeason?.name}
          </h2>
          <PersonalEvolution
            entries={evolution.entries}
            displayName={me.display_name}
          />
        </section>
      )}

      {/* Change password */}
      <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
        <h2 className="mb-4 text-lg font-semibold text-vpv-text">
          Cambiar contraseña
        </h2>

        {error && (
          <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-3 text-sm text-green-400">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="current"
              className="mb-1 block text-sm text-vpv-text-muted"
            >
              Contraseña actual
            </label>
            <input
              id="current"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              className="w-full rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="new"
              className="mb-1 block text-sm text-vpv-text-muted"
            >
              Nueva contraseña
            </label>
            <input
              id="new"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              className="w-full rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
            />
            <p className="mt-1 text-xs text-vpv-text-muted">Minimo 8 caracteres</p>
          </div>
          <div>
            <label
              htmlFor="confirm"
              className="mb-1 block text-sm text-vpv-text-muted"
            >
              Confirmar nueva contraseña
            </label>
            <input
              id="confirm"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              className="w-full rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={saving || !currentPassword || !newPassword || !confirmPassword}
            className="rounded-lg bg-vpv-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
          >
            {saving ? "Guardando..." : "Cambiar contraseña"}
          </button>
        </form>
      </section>
    </div>
  );
}
