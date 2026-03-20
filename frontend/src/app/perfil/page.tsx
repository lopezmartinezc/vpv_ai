"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient } from "@/lib/api-client";
import { PersonalEvolution } from "@/components/standings/personal-evolution";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type {
  AccuracyResponse,
  EvolutionEntry,
  LineupHistoryResponse,
} from "@/types";

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
  permissions: number;
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

  const { data: accuracy } = useFetch<AccuracyResponse>(
    user && selectedSeason
      ? `/lineups/${selectedSeason.id}/accuracy`
      : null,
  );

  const [expandedMd, setExpandedMd] = useState<number | null>(null);
  const [expandedAccMd, setExpandedAccMd] = useState<number | null>(null);
  const [showPassword, setShowPassword] = useState(false);

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

      {/* Change password (accordion) */}
      <section className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden">
        <button
          type="button"
          onClick={() => setShowPassword(!showPassword)}
          className="flex w-full items-center justify-between px-5 py-3 text-left transition-colors hover:bg-vpv-bg/50"
        >
          <span className="text-sm font-semibold text-vpv-text">
            Cambiar contraseña
          </span>
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            className={`text-vpv-text-muted transition-transform ${showPassword ? "rotate-180" : ""}`}
          >
            <path
              d="M4 6l4 4 4-4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        {showPassword && (
          <div className="border-t border-vpv-border px-5 py-4">
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
                <label htmlFor="current" className="mb-1 block text-sm text-vpv-text-muted">
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
                <label htmlFor="new" className="mb-1 block text-sm text-vpv-text-muted">
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
                <label htmlFor="confirm" className="mb-1 block text-sm text-vpv-text-muted">
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
          </div>
        )}
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

      {/* Accuracy — Acierto de Mister */}
      {accuracy && accuracy.matchdays.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-vpv-text">
            Acierto de Mister
          </h2>
          {/* Summary cards */}
          <div className="mb-3 grid grid-cols-3 gap-2">
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-3 py-2 text-center">
              <p
                className={`text-xl font-bold tabular-nums ${
                  accuracy.avg_accuracy >= 90
                    ? "text-emerald-400"
                    : accuracy.avg_accuracy >= 70
                      ? "text-amber-400"
                      : "text-red-400"
                }`}
              >
                {accuracy.avg_accuracy}%
              </p>
              <p className="text-[10px] text-vpv-text-muted">Acierto medio</p>
            </div>
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-3 py-2 text-center">
              <p className="text-xl font-bold tabular-nums text-vpv-text">
                {accuracy.perfect_weeks}
              </p>
              <p className="text-[10px] text-vpv-text-muted">Semanas perfectas</p>
            </div>
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-3 py-2 text-center">
              <p className="text-xl font-bold tabular-nums text-red-400">
                -{accuracy.total_missed_points}
              </p>
              <p className="text-[10px] text-vpv-text-muted">Puntos perdidos</p>
            </div>
          </div>

          {/* Per-matchday list */}
          <div className="space-y-1.5">
            {accuracy.matchdays.map((md) => {
              const isExpanded = expandedAccMd === md.matchday_number;
              const barColor =
                md.accuracy_pct >= 90
                  ? "bg-emerald-500"
                  : md.accuracy_pct >= 70
                    ? "bg-amber-400"
                    : "bg-red-500";
              return (
                <div
                  key={md.matchday_number}
                  className="rounded-lg border border-vpv-card-border bg-vpv-card overflow-hidden"
                >
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedAccMd(
                        isExpanded ? null : md.matchday_number,
                      )
                    }
                    className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-vpv-bg/50"
                  >
                    <span className="text-xs font-bold text-vpv-accent w-7">
                      J{md.matchday_number}
                    </span>
                    {/* Progress bar */}
                    <div className="flex-1">
                      <div className="h-2 rounded-full bg-vpv-border overflow-hidden">
                        <div
                          className={`h-full rounded-full ${barColor}`}
                          style={{ width: `${Math.min(100, md.accuracy_pct)}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs tabular-nums text-vpv-text-muted w-16 text-right">
                      {md.actual_points}/{md.optimal_points}
                    </span>
                    <span
                      className={`text-xs font-bold tabular-nums w-10 text-right ${
                        md.accuracy_pct >= 90
                          ? "text-emerald-400"
                          : md.accuracy_pct >= 70
                            ? "text-amber-400"
                            : "text-red-400"
                      }`}
                    >
                      {md.accuracy_pct}%
                    </span>
                    <svg
                      width="12"
                      height="12"
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
                  </button>

                  {isExpanded && md.missed_calls.length > 0 && (
                    <div className="border-t border-vpv-border px-3 py-2 space-y-1">
                      {md.formation_used !== md.optimal_formation && (
                        <p className="text-[10px] text-vpv-text-muted">
                          Formacion optima: {md.optimal_formation} (pusiste {md.formation_used})
                        </p>
                      )}
                      {md.missed_calls.map((mc, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-1.5 text-[11px]"
                        >
                          <span
                            className={`rounded border px-1 py-px text-[9px] font-bold ${POS_COLORS[mc.position] ?? "text-vpv-text-muted border-vpv-border"}`}
                          >
                            {mc.position}
                          </span>
                          <span className="text-red-400">
                            {mc.lined_up_name} ({mc.lined_up_points})
                          </span>
                          <span className="text-vpv-text-muted">→</span>
                          <span className="text-emerald-400">
                            {mc.benched_name} ({mc.benched_points})
                          </span>
                          <span className="text-vpv-text-muted">
                            +{mc.benched_points - mc.lined_up_points}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {isExpanded && md.missed_calls.length === 0 && (
                    <div className="border-t border-vpv-border px-3 py-2">
                      <p className="text-[11px] text-emerald-400">
                        Alineacion perfecta
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
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

    </div>
  );
}
