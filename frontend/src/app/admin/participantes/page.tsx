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
  );
}
