"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

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
  group_name: string | null;
}

interface AdminUser {
  id: number;
  username: string;
  display_name: string;
}

const GROUPS = [
  "Virtuales",
  "Petit Comite",
  "Vacas Sagradas",
  "Comando Badalona",
] as const;

export default function AdminParticipantesPage() {
  const [seasons, setSeasons] = useState<SeasonSummary[]>([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);
  const [participants, setParticipants] = useState<SeasonParticipant[]>([]);
  const [loading, setLoading] = useState(true);
  const [participantsLoading, setParticipantsLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [allUsers, setAllUsers] = useState<AdminUser[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSeasons() {
      try {
        const data = await apiClient.get<SeasonSummary[]>("/seasons");
        setSeasons(data);
        if (data.length > 0) {
          const active = data.find((s) => s.status === "active") ?? data[0];
          setSelectedSeasonId(active.id);
        }
      } catch {
        // handled by auth context
      } finally {
        setLoading(false);
      }
    }
    fetchSeasons();
  }, []);

  const fetchParticipants = useCallback(async (seasonId: number) => {
    setParticipantsLoading(true);
    try {
      const data = await apiClient.get<SeasonParticipant[]>(
        `/seasons/${seasonId}/participants`
      );
      setParticipants(data);
    } catch {
      setParticipants([]);
    } finally {
      setParticipantsLoading(false);
    }
  }, []);

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
        {}
      );
      setParticipants((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p))
      );
    } catch {
      // error
    } finally {
      setTogglingId(null);
    }
  }

  async function openAddModal() {
    setShowAddModal(true);
    setSelectedUserId(null);
    setMessage(null);
    if (allUsers.length === 0) {
      try {
        const users = await apiClient.get<AdminUser[]>("/auth/admin/users");
        setAllUsers(users);
      } catch {
        setMessage("Error cargando usuarios");
      }
    }
  }

  async function handleAddParticipant() {
    if (!selectedSeasonId || !selectedUserId) return;
    setAdding(true);
    setMessage(null);
    try {
      await apiClient.post(
        `/seasons/admin/${selectedSeasonId}/participants`,
        { user_id: selectedUserId },
      );
      setShowAddModal(false);
      await fetchParticipants(selectedSeasonId);
      setMessage("Participante anadido");
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error";
      setMessage(msg);
    } finally {
      setAdding(false);
    }
  }

  // Users not yet participants in this season
  const availableUsers = allUsers.filter(
    (u) => !participants.some((p) => p.user_id === u.id),
  );

  async function handleGroupChange(
    participantId: number,
    groupName: string | null
  ) {
    if (selectedSeasonId === null) return;
    try {
      const updated = await apiClient.put<SeasonParticipant>(
        `/seasons/admin/${selectedSeasonId}/participants/${participantId}/group`,
        { group_name: groupName }
      );
      setParticipants((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p))
      );
    } catch {
      // error
    }
  }

  if (loading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-10 animate-pulse rounded-lg bg-vpv-border"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {message && (
        <div className="rounded border border-vpv-border bg-vpv-bg px-4 py-2 text-sm text-vpv-text">
          {message}
        </div>
      )}

      {showAddModal && (
        <div className="rounded-lg border border-green-600/30 bg-vpv-card">
          <div className="border-b border-vpv-border px-4 py-3">
            <h2 className="font-semibold text-vpv-text">Anadir participante</h2>
          </div>
          <div className="space-y-3 px-4 py-3">
            <div>
              <label className="mb-1 block text-xs text-vpv-text-muted">
                Usuario
              </label>
              <select
                value={selectedUserId ?? ""}
                onChange={(e) =>
                  setSelectedUserId(e.target.value ? Number(e.target.value) : null)
                }
                className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
              >
                <option value="">— Selecciona un usuario —</option>
                {availableUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.display_name} ({u.username})
                  </option>
                ))}
              </select>
              {availableUsers.length === 0 && allUsers.length > 0 && (
                <p className="mt-1 text-xs text-vpv-text-muted">
                  Todos los usuarios ya son participantes.
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleAddParticipant}
                disabled={adding || !selectedUserId}
                className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
              >
                {adding ? "Anadiendo..." : "Anadir"}
              </button>
              <button
                onClick={() => setShowAddModal(false)}
                className="rounded border border-vpv-border px-3 py-1.5 text-xs text-vpv-text-muted transition-colors hover:bg-vpv-bg"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-center justify-between border-b border-vpv-border px-4 py-3">
        <h2 className="font-semibold text-vpv-text">
          Participantes por temporada
        </h2>
        <div className="flex items-center gap-2">
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
          <button
            onClick={openAddModal}
            className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-700"
          >
            + Anadir
          </button>
        </div>
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
              <div key={p.id} className="space-y-2 px-4 py-3">
                <div className="flex items-center justify-between">
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
                  <div className="flex items-center gap-2">
                    {p.is_active ? (
                      <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-600">
                        Activo
                      </span>
                    ) : (
                      <span className="rounded bg-vpv-danger/20 px-2 py-0.5 text-xs font-medium text-vpv-danger">
                        Inactivo
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={p.group_name ?? ""}
                    onChange={(e) =>
                      handleGroupChange(p.id, e.target.value || null)
                    }
                    className="flex-1 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-xs text-vpv-text"
                  >
                    <option value="">Sin grupo</option>
                    {GROUPS.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleToggleActive(p.id)}
                    disabled={togglingId === p.id}
                    className={`rounded px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                      p.is_active
                        ? "border border-vpv-danger/30 text-vpv-danger hover:bg-vpv-danger/10"
                        : "border border-green-500/30 text-green-600 hover:bg-green-500/10"
                    }`}
                  >
                    {p.is_active ? "Desactivar" : "Activar"}
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
                  <th className="px-4 py-2">Nombre</th>
                  <th className="px-4 py-2">Orden draft</th>
                  <th className="px-4 py-2">Grupo</th>
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
                      {p.draft_order !== null ? `#${p.draft_order}` : "\u2014"}
                    </td>
                    <td className="px-4 py-2">
                      <select
                        value={p.group_name ?? ""}
                        onChange={(e) =>
                          handleGroupChange(p.id, e.target.value || null)
                        }
                        className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
                      >
                        <option value="">Sin grupo</option>
                        {GROUPS.map((g) => (
                          <option key={g} value={g}>
                            {g}
                          </option>
                        ))}
                      </select>
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
