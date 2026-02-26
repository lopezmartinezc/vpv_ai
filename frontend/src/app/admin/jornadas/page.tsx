"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface SeasonDetail {
  id: number;
  name: string;
  status: string;
  matchday_start: number;
  matchday_current: number;
}

interface MatchdaySummary {
  number: number;
  status: string;
  counts: boolean;
  stats_ok: boolean;
  first_match_at: string | null;
}

interface MatchEntry {
  id: number;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  counts: boolean;
  played_at: string | null;
}

interface MatchdayDetailData {
  season_id: number;
  number: number;
  status: string;
  counts: boolean;
  stats_ok: boolean;
  matches: MatchEntry[];
}

export default function AdminJornadasPage() {
  const [seasons, setSeasons] = useState<SeasonDetail[]>([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);
  const [matchdays, setMatchdays] = useState<MatchdaySummary[]>([]);
  const [expandedMd, setExpandedMd] = useState<number | null>(null);
  const [matchdayDetail, setMatchdayDetail] =
    useState<MatchdayDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const selectedSeason = seasons.find((s) => s.id === selectedSeasonId) ?? null;

  const fetchSeasons = useCallback(async () => {
    try {
      const data = await apiClient.get<SeasonDetail[]>("/seasons");
      setSeasons(data);
      if (data.length > 0 && selectedSeasonId === null) {
        const active = data.find((s) => s.status === "active") ?? data[0];
        setSelectedSeasonId(active.id);
      }
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  }, [selectedSeasonId]);

  const fetchMatchdays = useCallback(async (seasonId: number) => {
    try {
      const data = await apiClient.get<{
        matchdays: MatchdaySummary[];
      }>(`/matchdays/${seasonId}?stats_ok_only=false`);
      setMatchdays(data.matchdays);
    } catch {
      // handled
    }
  }, []);

  useEffect(() => {
    fetchSeasons();
  }, [fetchSeasons]);

  useEffect(() => {
    if (selectedSeasonId !== null) {
      fetchMatchdays(selectedSeasonId);
      setExpandedMd(null);
      setMatchdayDetail(null);
    }
  }, [selectedSeasonId, fetchMatchdays]);

  async function handleExpandMatchday(number: number) {
    if (expandedMd === number) {
      setExpandedMd(null);
      setMatchdayDetail(null);
      return;
    }
    setExpandedMd(number);
    try {
      const detail = await apiClient.get<MatchdayDetailData>(
        `/matchdays/${selectedSeasonId}/${number}`,
      );
      setMatchdayDetail(detail);
    } catch {
      // handled
    }
  }

  async function handleToggleMatchdayCounts(
    number: number,
    currentCounts: boolean,
  ) {
    if (!selectedSeasonId) return;
    setActionLoading(`md-${number}`);
    try {
      await apiClient.put(
        `/matchdays/admin/${selectedSeasonId}/${number}`,
        { counts: !currentCounts },
      );
      await fetchMatchdays(selectedSeasonId);
      if (expandedMd === number && matchdayDetail) {
        setMatchdayDetail({ ...matchdayDetail, counts: !currentCounts });
      }
      showMessage(`J${number}: counts = ${!currentCounts}`);
    } catch {
      showMessage("Error al actualizar jornada");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleToggleMatchCounts(
    matchId: number,
    currentCounts: boolean,
  ) {
    if (!selectedSeasonId || !expandedMd) return;
    setActionLoading(`match-${matchId}`);
    try {
      const updated = await apiClient.put<MatchEntry>(
        `/matchdays/admin/${selectedSeasonId}/${expandedMd}/match/${matchId}`,
        { counts: !currentCounts },
      );
      if (matchdayDetail) {
        setMatchdayDetail({
          ...matchdayDetail,
          matches: matchdayDetail.matches.map((m) =>
            m.id === matchId ? { ...m, counts: updated.counts } : m,
          ),
        });
      }
      showMessage(`Partido ${matchId}: counts = ${!currentCounts}`);
    } catch {
      showMessage("Error al actualizar partido");
    } finally {
      setActionLoading(null);
    }
  }

  function showMessage(msg: string) {
    setMessage(msg);
    setTimeout(() => setMessage(null), 3000);
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "\u2014";
    return new Date(iso).toLocaleDateString("es-ES", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
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

  const preStartCount = selectedSeason
    ? matchdays.filter(
        (md) => md.number < selectedSeason.matchday_start && md.counts,
      ).length
    : 0;

  return (
    <div className="space-y-4">
      {/* Season selector */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-vpv-text-muted">Temporada:</label>
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
        {selectedSeason && (
          <span className="text-xs text-vpv-text-muted">
            Inicio: J{selectedSeason.matchday_start} | Actual: J
            {selectedSeason.matchday_current}
          </span>
        )}
        {message && (
          <span className="text-xs text-vpv-text-muted">{message}</span>
        )}
      </div>

      {/* Pre-start info */}
      {preStartCount > 0 && selectedSeason && (
        <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-4 py-2">
          <span className="text-sm text-yellow-400">
            {preStartCount} jornada(s) antes de J
            {selectedSeason.matchday_start} aun tienen counts=true.
            Cambia la jornada inicial en Temporadas para sincronizar
            automaticamente.
          </span>
        </div>
      )}

      {/* Matchdays list */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Jornadas ({matchdays.length})
          </h2>
        </div>
        <div className="divide-y divide-vpv-border">
          {matchdays.map((md) => {
            const isPreStart =
              selectedSeason !== null &&
              md.number < selectedSeason.matchday_start;
            return (
              <div
                key={md.number}
                className={isPreStart ? "opacity-60" : ""}
              >
                <div className="flex items-center gap-3 px-4 py-2">
                  <button
                    onClick={() => handleExpandMatchday(md.number)}
                    className="flex-1 text-left"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-medium text-vpv-text">
                        J{md.number}
                      </span>
                      <span className="text-xs text-vpv-text-muted">
                        {formatDate(md.first_match_at)}
                      </span>
                      <div className="flex items-center gap-1">
                        {isPreStart && (
                          <span className="rounded bg-vpv-text-muted/20 px-1.5 py-0.5 text-xs text-vpv-text-muted">
                            Antes de inicio
                          </span>
                        )}
                        {md.stats_ok && (
                          <span className="rounded bg-green-500/20 px-1.5 py-0.5 text-xs text-green-400">
                            Stats OK
                          </span>
                        )}
                        {!md.counts && (
                          <span className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-400">
                            No computa
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-vpv-text-muted">
                        {expandedMd === md.number ? "\u25B2" : "\u25BC"}
                      </span>
                    </div>
                  </button>
                  <button
                    onClick={() =>
                      handleToggleMatchdayCounts(md.number, md.counts)
                    }
                    disabled={actionLoading === `md-${md.number}`}
                    className={`rounded px-2 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                      md.counts
                        ? "bg-green-600/20 text-green-400 hover:bg-green-600/30"
                        : "bg-red-600/20 text-red-400 hover:bg-red-600/30"
                    }`}
                  >
                    {md.counts ? "Computa" : "No computa"}
                  </button>
                </div>

                {/* Expanded matches */}
                {expandedMd === md.number && matchdayDetail && (
                  <div className="border-t border-vpv-border bg-vpv-bg/50 px-4 py-2">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-vpv-text-muted">
                          <th className="py-1">Partido</th>
                          <th className="py-1 text-center">Resultado</th>
                          <th className="py-1 text-center">Fecha</th>
                          <th className="py-1 text-right">Computa</th>
                        </tr>
                      </thead>
                      <tbody>
                        {matchdayDetail.matches.map((match) => (
                          <tr
                            key={match.id}
                            className="border-t border-vpv-border/50"
                          >
                            <td className="py-1.5 text-vpv-text">
                              {match.home_team} vs {match.away_team}
                            </td>
                            <td className="py-1.5 text-center text-vpv-text">
                              {match.home_score !== null
                                ? `${match.home_score} - ${match.away_score}`
                                : "\u2014"}
                            </td>
                            <td className="py-1.5 text-center text-xs text-vpv-text-muted">
                              {formatDate(match.played_at)}
                            </td>
                            <td className="py-1.5 text-right">
                              <button
                                onClick={() =>
                                  handleToggleMatchCounts(
                                    match.id,
                                    match.counts,
                                  )
                                }
                                disabled={
                                  actionLoading === `match-${match.id}`
                                }
                                className={`rounded px-2 py-0.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                                  match.counts
                                    ? "bg-green-600/20 text-green-400 hover:bg-green-600/30"
                                    : "bg-red-600/20 text-red-400 hover:bg-red-600/30"
                                }`}
                              >
                                {match.counts ? "Si" : "No"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
