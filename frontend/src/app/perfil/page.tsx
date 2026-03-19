"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient } from "@/lib/api-client";
import { PersonalEvolution } from "@/components/standings/personal-evolution";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { EvolutionEntry, LineupHistoryResponse } from "@/types";

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

const POS_COLORS: Record<string, string> = {
  POR: "text-amber-400 border-amber-400/30",
  DEF: "text-blue-400 border-blue-400/30",
  MED: "text-green-400 border-green-400/30",
  DEL: "text-red-400 border-red-400/30",
};

export default function PerfilPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason } = useSeason();
  const { data: me } = useFetch<MeResponse>(user ? "/auth/me" : null);
  const { data: evolution } = useFetch<EvolutionResponse>(
    selectedSeason ? `/standings/${selectedSeason.id}/evolution` : null,
  );
  const { data: history } = useFetch<LineupHistoryResponse>(
    user && selectedSeason
      ? `/lineups/${selectedSeason.id}/history`
      : null,
  );

  const [expandedMd, setExpandedMd] = useState<number | null>(null);

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
      setError("La nueva contrasena debe tener al menos 8 caracteres");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Las contrasenas no coinciden");
      return;
    }
    if (currentPassword === newPassword) {
      setError("La nueva contrasena debe ser diferente a la actual");
      return;
    }

    setSaving(true);
    try {
      await apiClient.put<{ message: string }>("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccess("Contrasena actualizada correctamente");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Error al cambiar la contrasena",
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

      {/* Lineup history */}
      {history && history.lineups.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-vpv-text">
            Historial de alineaciones
          </h2>
          <div className="space-y-2">
            {history.lineups.map((lineup) => {
              const isExpanded = expandedMd === lineup.matchday_number;
              return (
                <div
                  key={lineup.matchday_number}
                  className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden"
                >
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedMd(isExpanded ? null : lineup.matchday_number)
                    }
                    className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-vpv-bg/50"
                  >
                    <div className="flex items-center gap-3">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-vpv-accent/10 text-sm font-bold text-vpv-accent">
                        J{lineup.matchday_number}
                      </span>
                      <div>
                        <span className="text-sm font-medium text-vpv-text">
                          {lineup.formation}
                        </span>
                        {lineup.confirmed_at && (
                          <p className="text-[11px] text-vpv-text-muted">
                            {new Date(lineup.confirmed_at).toLocaleDateString(
                              "es-ES",
                              { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" },
                            )}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-bold tabular-nums text-vpv-text">
                        {lineup.total_points}
                      </span>
                      <span className="text-[10px] text-vpv-text-muted">pts</span>
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 16 16"
                        fill="none"
                        className={`text-vpv-text-muted transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      >
                        <path
                          d="M4 6l4 4 4-4"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-vpv-border px-4 py-3">
                      <div className="space-y-1.5">
                        {lineup.players.map((p) => (
                          <div
                            key={p.player_id}
                            className="flex items-center gap-2.5"
                          >
                            <PlayerAvatar
                              photoPath={p.photo_path}
                              name={p.player_name}
                              size={28}
                            />
                            <span
                              className={`rounded border px-1 py-px text-[9px] font-bold ${POS_COLORS[p.position_slot] ?? "text-vpv-text-muted border-vpv-border"}`}
                            >
                              {p.position_slot}
                            </span>
                            <span className="flex-1 truncate text-sm text-vpv-text">
                              {p.player_name}
                            </span>
                            <span className="text-sm font-medium tabular-nums text-vpv-text-muted">
                              {p.points}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Change password */}
      <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
        <h2 className="mb-4 text-lg font-semibold text-vpv-text">
          Cambiar contrasena
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
              Contrasena actual
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
              Nueva contrasena
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
              Confirmar nueva contrasena
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
            {saving ? "Guardando..." : "Cambiar contrasena"}
          </button>
        </form>
      </section>
    </div>
  );
}
